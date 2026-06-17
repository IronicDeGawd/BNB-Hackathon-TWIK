"""Tests for the CMC structural veto — pure decision + no-key fault tolerance. No network."""

from config import settings
from signals.cmc import _structural_ok, collect, CmcSignal

THIN = settings.CMC_MIN_LIQUIDITY_USD - 1
DEEP = settings.CMC_MIN_LIQUIDITY_USD * 10
HOT_FUNDING = settings.CMC_MAX_FUNDING_ABS + 0.01


def test_thin_liquidity_vetoes():
    ok, reason = _structural_ok(THIN, None, "long")
    assert ok is False and "thin liquidity" in reason


def test_deep_liquidity_passes():
    ok, _ = _structural_ok(DEEP, None, "long")
    assert ok is True


def test_missing_liquidity_never_vetoes():
    # veto-only layer: unknown data must NOT block
    assert _structural_ok(None, None, "long")[0] is True


def test_funding_vetoes_long_when_crowded():
    ok, reason = _structural_ok(DEEP, HOT_FUNDING, "long")
    assert ok is False and "funding" in reason


def test_funding_ok_when_aligned():
    # high positive funding does not veto an exit
    assert _structural_ok(DEEP, HOT_FUNDING, "exit")[0] is True


def test_collect_without_key_is_passive(monkeypatch):
    monkeypatch.delenv("CMC_API_KEY", raising=False)
    out = collect(["CAKE", "AVAX"], {})
    assert set(out) == {"CAKE", "AVAX"}
    assert all(isinstance(v, CmcSignal) and v.structural_ok for v in out.values())
