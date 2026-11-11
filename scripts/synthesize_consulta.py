"""Gera `consulta_p0001.wav` e `hello_ptbr.wav` com o texto para fala da Azure (T37, passo 10).

A consulta segue o roteiro da seção 7.2 do plano, com duas vozes neurais pt-BR (a médica e o
paciente "seu João") e tosses **reais** inseridas depois da fala do paciente. As tosses vêm de
clipes **reservados** do ESC-50 (folds 4–5): usar o reservado na demonstração é permitido; ajustar
parâmetros com ele, não.

Limitação: numa voz sintética a análise de fadiga e de alteração da fala (jitter, pausas, F0) não
tem sentido clínico. Essa análise deve ser demonstrada com vozes reais (Common Voice, passo 9).
A transcrição, os termos críticos, o sentimento e os sons respiratórios valem normalmente.

Uso:
  python scripts/synthesize_consulta.py                 # consulta + hello em data/samples
  python scripts/synthesize_consulta.py --no-coughs     # sem tosses (ESC-50 não baixado)
  python scripts/synthesize_consulta.py --only hello

Requer AZURE_SPEECH_KEY/AZURE_SPEECH_REGION no .env e USE_FAKE_AZURE=false.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SR = 16000
DOCTOR_VOICE = "pt-BR-FranciscaNeural"   # médica
PATIENT_VOICE = "pt-BR-AntonioNeural"    # paciente "seu João"
RESERVED_FOLDS = ("4", "5")              # ESC-50: folds reservados (config/splits.yaml)

# (voz, texto, ritmo em %, número de tosses depois da fala)
Synthesizer = Callable[[str, str, int], np.ndarray]


@dataclass(frozen=True)
class Fala:
    voice: str
    text: str
    rate: int = 0
    coughs_after: int = 0


CONSULTA = [
    Fala(DOCTOR_VOICE, "Bom dia, seu João. Como o senhor passou a noite?"),
    Fala(PATIENT_VOICE, "Mal, doutora. Estou com falta de ar desde ontem e um cansaço muito grande.", -20),
    Fala(DOCTOR_VOICE, "O senhor teve febre? Sentiu dor no peito?"),
    Fala(PATIENT_VOICE,
         "Febre não sei, mas tenho tossido bastante e dói um pouco no peito quando tusso.", -20,
         coughs_after=2),
    Fala(DOCTOR_VOICE, "Consegue subir escada?"),
    Fala(PATIENT_VOICE, "Não, fico sem fôlego logo no começo.", -25),
]
HELLO = [Fala(DOCTOR_VOICE, "Olá, este é um teste do MedWatch.")]


def build_ssml(voice: str, text: str, rate: int = 0) -> str:
    """SSML de uma fala. Em ritmo lento (paciente), acrescenta pausas depois das vírgulas."""
    body = escape(text)
    if rate < 0:
        body = body.replace(", ", ', <break time="450ms"/>')
    return (
        "<speak version='1.0' xml:lang='pt-BR' xmlns='http://www.w3.org/2001/10/synthesis'>"
        f"<voice name='{voice}'><prosody rate='{rate:+d}%'>{body}</prosody></voice></speak>"
    )


class AzureSynthesizer:
    """Texto para fala da Azure; devolve áudio mono float32 a 16 kHz."""

    def __init__(self, key: str, region: str) -> None:
        import azure.cognitiveservices.speech as speechsdk

        self._sdk = speechsdk
        cfg = speechsdk.SpeechConfig(subscription=key, region=region)
        cfg.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm)
        self._synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)

    def __call__(self, voice: str, text: str, rate: int = 0) -> np.ndarray:
        result = self._synth.speak_ssml_async(build_ssml(voice, text, rate)).get()
        if result.reason != self._sdk.ResultReason.SynthesizingAudioCompleted:
            detail = result.cancellation_details
            raise RuntimeError(f"síntese falhou: {detail.reason} {detail.error_details}")
        data, sr = sf.read(io.BytesIO(result.audio_data), dtype="float32")
        if sr != SR:
            raise RuntimeError(f"taxa inesperada: {sr}")
        return data


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), dtype="float32")


def load_coughs(esc50_dir: Path, n: int) -> list[np.ndarray]:
    """Carrega `n` tosses de clipes reservados do ESC-50, cortadas ao trecho com som, a 16 kHz."""
    import librosa

    meta = esc50_dir / "meta" / "esc50.csv"
    if not meta.exists():
        raise FileNotFoundError(f"{meta} ausente: rode scripts/download_datasets.py --esc50")
    with meta.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["category"] == "coughing" and r["fold"] in RESERVED_FOLDS]
    rows.sort(key=lambda r: r["filename"])
    clips = []
    for r in rows[:n]:
        y, sr = sf.read(esc50_dir / "audio" / r["filename"], dtype="float32")
        if y.ndim > 1:
            y = y.mean(axis=1)
        y = librosa.resample(y, orig_sr=sr, target_sr=SR)
        y, _ = librosa.effects.trim(y, top_db=30)
        peak = float(np.max(np.abs(y))) or 1.0
        clips.append((y / peak * 0.6).astype("float32"))
    return clips


def assemble(falas: list[Fala], synth: Synthesizer, coughs: list[np.ndarray] | None = None,
             gap_s: float = 0.6, cough_gap_s: float = 0.35) -> np.ndarray:
    """Concatena as falas com pausas e insere as tosses depois das falas que as pedem."""
    coughs = coughs or []
    parts: list[np.ndarray] = [silence(0.3)]
    cough_i = 0
    for f in falas:
        parts.append(synth(f.voice, f.text, f.rate))
        if coughs:
            for _ in range(f.coughs_after):
                parts += [silence(cough_gap_s), coughs[cough_i % len(coughs)]]
                cough_i += 1
        parts.append(silence(gap_s))
    return np.concatenate(parts)


def write_wav(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, SR, subtype="PCM_16")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "samples")
    ap.add_argument("--esc50-dir", type=Path, default=ROOT / "data" / "datasets" / "esc50")
    ap.add_argument("--coughs", type=int, default=3, help="quantas tosses reservadas carregar")
    ap.add_argument("--no-coughs", action="store_true")
    ap.add_argument("--only", choices=["consulta", "hello"])
    args = ap.parse_args(argv)

    from medwatch.config import get_settings

    st = get_settings()
    if st.use_fake_azure or not st.azure_speech_key:
        print("Defina AZURE_SPEECH_KEY/AZURE_SPEECH_REGION e USE_FAKE_AZURE=false no .env.",
              file=sys.stderr)
        return 1
    synth = AzureSynthesizer(st.azure_speech_key, st.azure_speech_region)

    if args.only != "consulta":
        out = args.out_dir / "hello_ptbr.wav"
        write_wav(out, assemble(HELLO, synth))
        print(f"ok {out}")
    if args.only != "hello":
        coughs = [] if args.no_coughs else load_coughs(args.esc50_dir, args.coughs)
        audio = assemble(CONSULTA, synth, coughs)
        out = args.out_dir / "consulta_p0001.wav"
        write_wav(out, audio)
        inseridas = sum(f.coughs_after for f in CONSULTA) if coughs else 0
        print(f"ok {out} ({len(audio) / SR:.1f} s, {inseridas} tosses reservadas do ESC-50 inseridas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
