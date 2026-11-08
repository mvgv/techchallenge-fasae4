"""Busca de termos críticos em texto (sem acento, sem diferenciar maiúsculas)."""
import re

from unidecode import unidecode


def _norm(text: str) -> str:
    return unidecode(text).lower()


def find_critical_terms(text: str, terms_cfg: dict | list) -> list[dict]:
    """Retorna {term, category, weight, start} por termo encontrado, sem duplicatas."""
    terms = terms_cfg.get("terms", []) if isinstance(terms_cfg, dict) else terms_cfg
    norm = _norm(text)
    found: list[dict] = []
    seen: set[str] = set()
    for t in terms:
        key = _norm(t["term"])
        if key in seen:
            continue
        m = re.search(rf"\b{re.escape(key)}\b", norm)
        if m:
            seen.add(key)
            found.append({"term": t["term"], "category": t["category"],
                          "weight": t["weight"], "start": m.start()})
    return sorted(found, key=lambda d: d["start"])
