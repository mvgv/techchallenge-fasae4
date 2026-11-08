from medwatch.audio.language import FakeLanguageAnalyzer, get_language_analyzer


def test_fake_negative_and_entities():
    r = FakeLanguageAnalyzer().analyze(["Estou com falta de ar e muito cansaço.", "Tudo certo hoje."])
    assert r.sentiments[0]["sentiment"] == "negative"
    assert r.sentiments[1]["sentiment"] == "neutral"
    assert r.health_entities[0][0]["category"] == "SymptomOrSign"
    assert len(r.key_phrases[0]) <= 3 and r.health_supported


def test_factory_fake(monkeypatch):
    from medwatch import config
    monkeypatch.setenv("USE_FAKE_AZURE", "true")
    config.get_settings.cache_clear()
    assert isinstance(get_language_analyzer(), FakeLanguageAnalyzer)
    config.get_settings.cache_clear()
