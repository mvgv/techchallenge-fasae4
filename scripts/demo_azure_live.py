"""Demonstração ao vivo da Azure: toca o áudio e mostra a transcrição aparecendo em paralelo.

O áudio é enviado à Azure Speech em ritmo real (blocos de 100 ms), como numa chamada ao vivo, e o
programa imprime as hipóteses parciais (linha que se reescreve) e os trechos finais, com o falante
e os termos críticos marcados. Ao final, com `--language`, chama a Azure Language (sentimento,
frases-chave e entidades de saúde).

Uso (precisa de AZURE_SPEECH_KEY e USE_FAKE_AZURE=false no .env):
    python scripts/demo_azure_live.py data/samples/consulta_p0001.wav
    python scripts/demo_azure_live.py data/samples/consulta_p0001.wav --language
    python scripts/demo_azure_live.py data/samples/consulta_p0001.wav --no-audio   # sem tocar (Linux/Mac)

No Windows o áudio sai pelo `winsound` (dispositivo padrão), sem dependência extra.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from medwatch.audio.convert import to_wav_16k_mono  # noqa: E402
from medwatch.audio.terms import find_critical_terms  # noqa: E402
from medwatch.config import get_settings, load_yaml  # noqa: E402

CHUNK_S = 0.1
BOLD, DIM, RED, GREEN, CYAN, RESET = "\033[1m", "\033[2m", "\033[91m", "\033[92m", "\033[96m", "\033[0m"


def play(wav: Path) -> None:
    """Toca o WAV sem bloquear (Windows)."""
    import winsound

    winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)


def stream_audio(wav: Path, push, realtime: bool = True) -> None:
    """Envia o PCM de 16 kHz mono à Azure em blocos de 100 ms, no ritmo da fala."""
    with wave.open(str(wav), "rb") as w:
        frames = int(w.getframerate() * CHUNK_S)
        while True:
            data = w.readframes(frames)
            if not data:
                break
            push.write(data)
            if realtime:
                time.sleep(CHUNK_S)
    push.close()


def mark_terms(text: str, terms: list[dict]) -> str:
    out = text
    for t in terms:
        i = out.lower().find(t["term"].lower())
        if i >= 0:
            out = out[:i] + f"{RED}{BOLD}{out[i:i + len(t['term'])]}{RESET}" + out[i + len(t["term"]):]
    return out


def run(wav_in: Path, with_language: bool, no_audio: bool) -> int:
    import azure.cognitiveservices.speech as speechsdk

    st = get_settings()
    if st.use_fake_azure or not st.azure_speech_key:
        print("Defina AZURE_SPEECH_KEY e USE_FAKE_AZURE=false no .env: usa a Azure de verdade.")
        return 2

    wav = to_wav_16k_mono(wav_in, ROOT / "data" / "tmp_demo_live.wav")
    terms_cfg = load_yaml("critical_terms")

    cfg = speechsdk.SpeechConfig(subscription=st.azure_speech_key, region=st.azure_speech_region)
    cfg.speech_recognition_language = st.speech_language
    fmt = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
    push = speechsdk.audio.PushAudioInputStream(stream_format=fmt)
    audio = speechsdk.audio.AudioConfig(stream=push)
    tr = speechsdk.transcription.ConversationTranscriber(speech_config=cfg, audio_config=audio)

    finals: list[tuple[str, str]] = []
    done = threading.Event()
    t0 = time.time()
    last_len = [0]

    def on_partial(evt):
        text = evt.result.text or ""
        line = f"{DIM}[{time.time() - t0:5.1f}s] ...{text}{RESET}"
        sys.stdout.write("\r" + line + " " * max(0, last_len[0] - len(line)))
        sys.stdout.flush()
        last_len[0] = len(line)

    def on_final(evt):
        r = evt.result
        if r.reason != speechsdk.ResultReason.RecognizedSpeech or not r.text:
            return
        speaker = r.speaker_id or "?"
        found = find_critical_terms(r.text, terms_cfg)
        finals.append((speaker, r.text))
        sys.stdout.write("\r" + " " * (last_len[0] + 10) + "\r")
        tag = f"{CYAN}{speaker}{RESET}"
        print(f"[{r.offset / 1e7:5.1f}s] {tag}: {mark_terms(r.text, found)}")
        for t in found:
            print(f"        {RED}termo crítico{RESET}: {t['term']} ({t['category']}, peso {t['weight']})")
        last_len[0] = 0

    def on_cancel(evt):
        d = getattr(evt, "error_details", None)
        if d:
            print(f"\n{RED}Azure cancelou: {d}{RESET}")
        done.set()

    tr.transcribing.connect(on_partial)
    tr.transcribed.connect(on_final)
    tr.canceled.connect(on_cancel)
    tr.session_stopped.connect(lambda evt: done.set())

    print(f"{BOLD}Azure Speech ao vivo{RESET}: {wav_in.name} "
          f"({st.speech_language}, região {st.azure_speech_region})\n")
    tr.start_transcribing_async().get()
    if not no_audio:
        play(wav)
    feeder = threading.Thread(target=stream_audio, args=(wav, push), daemon=True)
    feeder.start()
    feeder.join()
    done.wait(timeout=30)
    tr.stop_transcribing_async().get()
    print(f"\n{GREEN}Transcrição concluída: {len(finals)} trechos em {time.time() - t0:.0f} s.{RESET}")

    if with_language and finals:
        from medwatch.audio.language import get_language_analyzer

        print(f"\n{BOLD}Azure Language{RESET} (sentimento, frases-chave, entidades de saúde)")
        res = get_language_analyzer().analyze([t for _, t in finals])
        for (spk, text), sent, kp, ents in zip(finals, res.sentiments, res.key_phrases,
                                              res.health_entities, strict=False):
            print(f"  {CYAN}{spk}{RESET} {text[:60]}")
            print(f"     sentimento: {sent['sentiment']} (neg {sent['negative']:.2f})")
            if kp:
                print(f"     frases-chave: {', '.join(kp[:5])}")
            if ents:
                nomes = ", ".join(e["text"] + " [" + e["category"] + "]" for e in ents[:5])
                print(f"     entidades: {nomes}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", type=Path, help="WAV, MP3 ou M4A de uma consulta")
    ap.add_argument("--language", action="store_true", help="depois da fala, chama a Azure Language")
    ap.add_argument("--no-audio", action="store_true", help="não toca o som (só mostra a transcrição)")
    a = ap.parse_args(argv)
    return run(a.audio, a.language, a.no_audio)


if __name__ == "__main__":
    sys.exit(main())
