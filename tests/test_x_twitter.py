from types import SimpleNamespace

import eaglesignal.ingestion.x_twitter as x


def test_x_usage_counter_and_budget(tmp_path, monkeypatch):
    fake = SimpleNamespace(data_dir=tmp_path, x_daily_read_budget=3, x_bearer_token=None)
    monkeypatch.setattr(x, "get_settings", lambda: fake)

    assert x.x_usage_today()["reads"] == 0
    assert x.x_budget_exhausted() is False

    for _ in range(3):
        x._record_read()

    u = x.x_usage_today()
    assert u["reads"] == 3
    assert u["est_cost_usd"] == round(3 * 0.005, 4)
    assert x.x_budget_exhausted() is True


def test_x_budget_zero_disables_cap(tmp_path, monkeypatch):
    fake = SimpleNamespace(data_dir=tmp_path, x_daily_read_budget=0)
    monkeypatch.setattr(x, "get_settings", lambda: fake)
    for _ in range(5):
        x._record_read()
    assert x.x_budget_exhausted() is False


def test_search_recent_without_token_is_unavailable(monkeypatch):
    fake = SimpleNamespace(x_bearer_token=None)
    monkeypatch.setattr(x, "get_settings", lambda: fake)
    res = x.search_recent("$NVDA")
    assert res.available is False
