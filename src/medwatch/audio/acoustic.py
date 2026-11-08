"""Features acústicas de voz e avaliação (fadiga, indicador de disartria)."""
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from medwatch.audio.speech import Segment

SR = 16000
Z_FEATURES = ("f0_mean", "f0_var", "jitter", "shimmer_db", "hnr", "loudness")
_SMILE_COLUMNS = {
    "f0_mean": "F0semitoneFrom27.5Hz_sma3nz_amean",
    "f0_var": "F0semitoneFrom27.5Hz_sma3nz_stddevNorm",
    "jitter": "jitterLocal_sma3nz_amean",
    "shimmer_db": "shimmerLocaldB_sma3nz_amean",
    "hnr": "HNRdBACF_sma3nz_amean",
    "loudness": "loudness_sma3_amean",
}


def _smile_features(wav: Path) -> dict:
    """openSMILE eGeMAPS; retorna None nas features indisponíveis."""
    out: dict = dict.fromkeys(_SMILE_COLUMNS)
    try:
        import opensmile

        smile = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.Functionals,
        )
        df = smile.process_file(str(wav))
    except Exception:  # noqa: BLE001 - opensmile ausente/incompatível: segue sem as features
        return out
    for key, col in _SMILE_COLUMNS.items():
        if col in df.columns:
            out[key] = float(df[col].iloc[0])
    return out


def extract_features(wav: Path, segments: list[Segment],
                     patient_speaker: str | None) -> dict:
    y, sr = librosa.load(str(wav), sr=SR)
    used = segments
    if patient_speaker is not None:
        used = [s for s in segments if s.speaker == patient_speaker]
        parts = [y[int(s.offset_s * sr):int((s.offset_s + s.duration_s) * sr)] for s in used]
        if parts:
            y = np.concatenate(parts)
    duration = len(y) / sr
    if len(y) > 0:
        intervals = librosa.effects.split(y, top_db=30)
        voiced = sum(int(e - s) for s, e in intervals) / sr
        pause_ratio = float(min(max(1 - voiced / duration, 0.0), 1.0))
    else:
        pause_ratio = 0.0
    words = sum(len(s.text.split()) for s in used)
    seg_time = sum(s.duration_s for s in used)
    wpm = words / (seg_time / 60) if seg_time > 0 else None

    tmp_path = None
    try:
        smile_wav = wav
        if patient_speaker is not None and len(y) > 0:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            sf.write(str(tmp_path), y, sr)
            smile_wav = tmp_path
        feats = _smile_features(smile_wav)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    feats.update(pause_ratio=pause_ratio, speech_rate_wpm=wpm, duration_s=float(duration))
    return feats


def zscore(feature: str, features: dict, baseline: dict | None) -> float | None:
    if not baseline or features.get(feature) is None or feature not in baseline:
        return None
    b = baseline[feature]
    return (features[feature] - b["mean"]) / max(b["std"], 1e-6)


def assess_voice(features: dict, baseline: dict | None,
                 cfg: dict) -> list[tuple[str, float, dict]]:
    zt = cfg.get("z_threshold", 2.0)
    z = {f: zscore(f, features, baseline) for f in Z_FEATURES}
    results: list[tuple[str, float, dict]] = []

    wpm = features.get("speech_rate_wpm")
    pr = features.get("pause_ratio")
    fatigue = {
        "slow_speech": wpm is not None and wpm < cfg["speech_rate_wpm_min"],
        "many_pauses": pr is not None and pr > cfg["pause_ratio_max"],
        "low_loudness": z["loudness"] is not None and z["loudness"] < -zt,
    }
    if sum(fatigue.values()) >= 2:
        flags = dict(fatigue, baseline_missing=baseline is None)
        results.append(("voice_fatigue", sum(fatigue.values()) / 3, flags))

    if baseline is not None:
        dys = {
            "jitter_high": z["jitter"] is not None and z["jitter"] > zt,
            "shimmer_high": z["shimmer_db"] is not None and z["shimmer_db"] > zt,
            "hnr_low": z["hnr"] is not None and z["hnr"] < -zt,
            "f0_monotone": z["f0_var"] is not None and z["f0_var"] < -zt,
        }
        if sum(dys.values()) >= 2:
            results.append(("voice_dysarthria_indicator", sum(dys.values()) / 4, dys))
    return results
