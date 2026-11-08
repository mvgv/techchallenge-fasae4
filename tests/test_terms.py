from medwatch.audio.terms import find_critical_terms
from medwatch.config import load_yaml


def test_accents_and_case():
    cfg = load_yaml("critical_terms")
    r = find_critical_terms("Sinto Falta de AR e muito cansaço, palpitação também", cfg)
    names = [x["term"] for x in r]
    assert "falta de ar" in names and "cansaco" in names and "palpitacao" in names


def test_no_duplicates_and_word_boundary():
    cfg = load_yaml("critical_terms")
    r = find_critical_terms("tosse, tosse e mais tosse; sem queda", cfg)
    assert [x["term"] for x in r].count("tosse") == 1
    assert find_critical_terms("tossexyz", cfg) == []
