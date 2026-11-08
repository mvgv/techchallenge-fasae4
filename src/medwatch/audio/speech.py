"""Transcrição de fala: Azure Speech ou cliente falso (USE_FAKE_AZURE=true)."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from medwatch.audio.convert import duration_seconds
from medwatch.config import get_settings


@dataclass
class Segment:
    speaker: str
    text: str
    offset_s: float
    duration_s: float


class Transcriber(Protocol):
    def transcribe(self, wav_path: Path) -> list[Segment]: ...


class AzureTranscriber:
    def __init__(self, key: str, region: str, language: str):
        self.key = key
        self.region = region
        self.language = language

    def transcribe(self, wav_path: Path) -> list[Segment]:
        import threading

        import azure.cognitiveservices.speech as speechsdk

        cfg = speechsdk.SpeechConfig(subscription=self.key, region=self.region)
        cfg.speech_recognition_language = self.language
        audio = speechsdk.audio.AudioConfig(filename=str(wav_path))
        tr = speechsdk.transcription.ConversationTranscriber(speech_config=cfg, audio_config=audio)
        segments: list[Segment] = []
        errors: list[str] = []
        done = threading.Event()

        def on_transcribed(evt):
            r = evt.result
            if r.reason == speechsdk.ResultReason.RecognizedSpeech and r.text:
                segments.append(Segment(r.speaker_id or "Unknown", r.text,
                                        r.offset / 1e7, r.duration / 1e7))

        def on_canceled(evt):
            details = getattr(evt, "error_details", None) or getattr(evt, "cancellation_details", None)
            if details and "EndOfStream" not in str(getattr(evt, "reason", "")):
                errors.append(str(details))
            done.set()

        tr.transcribed.connect(on_transcribed)
        tr.canceled.connect(on_canceled)
        tr.session_stopped.connect(lambda evt: done.set())
        tr.start_transcribing_async().get()
        finished = done.wait(timeout=max(120, duration_seconds(wav_path) * 3))
        tr.stop_transcribing_async().get()
        if errors and not segments:
            raise RuntimeError(f"Azure Speech falhou: {errors[0]}")
        if not finished:
            raise TimeoutError("Transcrição excedeu o tempo limite")
        return sorted(segments, key=lambda s: s.offset_s)


class FakeTranscriber:
    """Retorna segmentos fixos; usado quando USE_FAKE_AZURE=true."""

    def transcribe(self, wav_path: Path) -> list[Segment]:
        return [
            Segment("Guest-1", "Bom dia, como o senhor está se sentindo hoje?", 0.5, 3.0),
            Segment("Guest-2", "Estou com falta de ar e muito cansaço desde ontem.", 4.0, 4.5),
            Segment("Guest-1", "Teve febre ou dor no peito?", 9.0, 2.0),
            Segment("Guest-2", "Um pouco de dor no peito quando tusso.", 11.5, 3.5),
        ]


def get_transcriber() -> Transcriber:
    s = get_settings()
    if s.use_fake_azure:
        return FakeTranscriber()
    if not s.azure_speech_key:
        raise RuntimeError("AZURE_SPEECH_KEY ausente. Defina no .env ou use USE_FAKE_AZURE=true")
    return AzureTranscriber(s.azure_speech_key, s.azure_speech_region, s.speech_language)
