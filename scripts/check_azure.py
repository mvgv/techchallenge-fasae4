"""Verifica a conectividade com os serviços Azure. Sai com 0 se tudo OK, 1 caso contrário."""
import sys
import uuid
from pathlib import Path

from medwatch.audio.speech import get_transcriber
from medwatch.config import get_settings

SAMPLE = Path("data/samples/hello_ptbr.wav")


def check_speech() -> None:
    if not SAMPLE.exists():
        print(f"[speech] pulado: grave {SAMPLE} (fala curta em pt-BR) para testar a transcrição")
        return
    segments = get_transcriber().transcribe(SAMPLE)
    if not segments:
        raise RuntimeError("nenhum segmento transcrito")
    print("[speech] OK:", " ".join(s.text for s in segments))


def check_language() -> None:
    s = get_settings()
    if not (s.azure_language_key and s.azure_language_endpoint):
        raise RuntimeError("AZURE_LANGUAGE_KEY/AZURE_LANGUAGE_ENDPOINT ausentes")
    from azure.ai.textanalytics import TextAnalyticsClient
    from azure.core.credentials import AzureKeyCredential

    client = TextAnalyticsClient(s.azure_language_endpoint, AzureKeyCredential(s.azure_language_key))
    doc = client.analyze_sentiment(["Estou com falta de ar e muito cansado."], language=s.language_code)[0]
    if doc.is_error:
        raise RuntimeError(str(doc.error))
    print(f"[language] OK: {doc.sentiment} {doc.confidence_scores}")


def check_storage() -> None:
    s = get_settings()
    if s.storage_backend != "azure":
        print("[storage] pulado: STORAGE_BACKEND != azure")
        return
    from medwatch.storage import AzureBlobStorage

    st = AzureBlobStorage(s.azure_storage_connection_string, s.azure_storage_container)
    key = f"check/{uuid.uuid4()}.txt"
    uri = st.put_bytes(b"medwatch", key)
    data = b"".join(st.open_stream(key))
    if data != b"medwatch":
        raise RuntimeError(f"conteúdo divergente em {uri}")
    print(f"[storage] OK: {uri}")


def main() -> int:
    if get_settings().use_fake_azure:
        print("modo fake: USE_FAKE_AZURE=true, nenhuma chamada real à Azure foi feita")
        return 0
    failed = []
    for name, fn in (("speech", check_speech), ("language", check_language), ("storage", check_storage)):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] FALHOU: {exc}")
            failed.append(name)
    if failed:
        print("Serviços com falha:", ", ".join(failed))
        return 1
    print("Tudo OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
