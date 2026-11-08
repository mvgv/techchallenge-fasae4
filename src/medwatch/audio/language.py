"""Análise de linguagem: Azure AI Language ou cliente falso (USE_FAKE_AZURE=true)."""
import logging
from dataclasses import dataclass
from typing import Protocol

from medwatch.audio.terms import _norm, find_critical_terms
from medwatch.config import get_settings, load_yaml

log = logging.getLogger(__name__)


@dataclass
class LanguageResult:
    sentiments: list[dict]
    key_phrases: list[list[str]]
    health_entities: list[list[dict]]
    health_supported: bool


class LanguageAnalyzer(Protocol):
    def analyze(self, texts: list[str]) -> LanguageResult: ...


def _chunks(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


class AzureLanguageAnalyzer:
    def __init__(self, endpoint: str, key: str, language: str):
        from azure.ai.textanalytics import TextAnalyticsClient
        from azure.core.credentials import AzureKeyCredential
        self.client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        self.language = language

    def analyze(self, texts: list[str]) -> LanguageResult:
        """Analisa sentimento, frases-chave e entidades de saúde."""
        docs = [t[:5000] for t in texts if t.strip()]
        sentiments, phrases, entities = [], [], []
        health_supported = True
        for batch in _chunks(docs, 10):
            for d in self.client.analyze_sentiment(batch, language=self.language):
                if d.is_error:
                    sentiments.append({"sentiment": "unknown", "positive": 0, "neutral": 0, "negative": 0})
                else:
                    cs = d.confidence_scores
                    sentiments.append({"sentiment": d.sentiment, "positive": cs.positive,
                                       "neutral": cs.neutral, "negative": cs.negative})
            for d in self.client.extract_key_phrases(batch, language=self.language):
                phrases.append([] if d.is_error else list(d.key_phrases))
            if health_supported:
                try:
                    poller = self.client.begin_analyze_healthcare_entities(batch, language=self.language)
                    for d in poller.result():
                        entities.append([] if d.is_error else [
                            {"text": e.text, "category": e.category, "confidence": e.confidence_score}
                            for e in d.entities])
                except Exception as exc:
                    log.warning("Entidades de saúde indisponíveis: %s", exc)
                    health_supported = False
        if not health_supported:
            entities = [[] for _ in docs]
        return LanguageResult(sentiments, phrases, entities, health_supported)


class FakeLanguageAnalyzer:
    """Heurística local; usada quando USE_FAKE_AZURE=true."""

    def analyze(self, texts: list[str]) -> LanguageResult:
        """Sentimento por palavras-chave, frases-chave simples e termos críticos como entidades."""
        cfg = load_yaml("critical_terms")
        sentiments, phrases, entities = [], [], []
        for t in (x for x in texts if x.strip()):
            n = _norm(t)
            if any(k in n for k in ("dor", "falta de ar", "cansa")):
                sentiments.append({"sentiment": "negative", "positive": 0.05,
                                   "neutral": 0.15, "negative": 0.8})
            else:
                sentiments.append({"sentiment": "neutral", "positive": 0.1,
                                   "neutral": 0.8, "negative": 0.1})
            phrases.append([w.strip(".,;!?") for w in t.split() if len(w.strip(".,;!?")) > 4][:3])
            entities.append([{"text": h["term"], "category": "SymptomOrSign", "confidence": 0.9}
                             for h in find_critical_terms(t, cfg)])
        return LanguageResult(sentiments, phrases, entities, True)


def get_language_analyzer() -> LanguageAnalyzer:
    """Fábrica: falso com USE_FAKE_AZURE=true, senão Azure AI Language."""
    s = get_settings()
    if s.use_fake_azure:
        return FakeLanguageAnalyzer()
    if not s.azure_language_key or not s.azure_language_endpoint:
        raise RuntimeError("AZURE_LANGUAGE_KEY/ENDPOINT ausentes. Defina no .env ou use USE_FAKE_AZURE=true")
    return AzureLanguageAnalyzer(s.azure_language_endpoint, s.azure_language_key, s.language_code)
