from types import SimpleNamespace

import eaglesignal.analysis.llm_sentiment as m


def _settings(**kw):
    base = dict(enable_llm_sentiment=False, advisor_provider="auto",
                ollama_base_url="", advisor_model="")
    base.update(kw)
    return SimpleNamespace(**base)


def test_parse_scores_object_array():
    out = m._parse_scores('[{"i":0,"s":0.8},{"i":1,"s":-0.5}]', 2)
    assert out == [0.8, -0.5]


def test_parse_scores_clamps_and_handles_junk():
    assert m._parse_scores("no json here", 3) is None
    out = m._parse_scores('[{"i":0,"s":5.0}]', 1)  # clamped to 1.0
    assert out == [1.0]


def test_disabled_returns_none_without_network(monkeypatch):
    # enable_llm_sentiment False -> never reaches out, always falls back.
    assert m.llm_sentiment_enabled(_settings()) is False
    assert m.classify_headlines(["AAPL beats earnings"], _settings()) is None


def test_enabled_but_no_ollama_base_is_disabled():
    # Flag on, but no Ollama configured -> still disabled (no base url).
    assert m.llm_sentiment_enabled(_settings(enable_llm_sentiment=True)) is False


def test_classify_empty_titles_returns_none():
    assert m.classify_headlines([], _settings(enable_llm_sentiment=True)) is None
