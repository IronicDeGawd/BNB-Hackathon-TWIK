"""Tests for the TWAK wrapper — dry-run path only (no real broadcasts, no subprocess)."""

import os

import pytest

from execution import twak


@pytest.fixture(autouse=True)
def force_dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    twak._reset_dry_run()
    yield
    twak._reset_dry_run()


def test_dry_run_trade_returns_tagged_sim_hash():
    h = twak.execute_trade("CAKE", "buy", 12.5)
    assert h.startswith("0xDRYRUN")
    assert len(h) == 66                       # matches a real tx hash length (0x + 64)


def test_sim_hashes_are_unique():
    a = twak.execute_trade("CAKE", "buy", 10)
    b = twak.execute_trade("CAKE", "buy", 10)
    assert a != b                             # nonce keeps them distinct


def test_bad_side_rejected():
    with pytest.raises(ValueError):
        twak.execute_trade("CAKE", "hodl", 10)


def test_live_rejects_offlist_symbol(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TWAK_WALLET_ADDRESS", "0xabc")
    twak._reset_dry_run()
    with pytest.raises(RuntimeError):
        twak.execute_trade("NOTATOKEN", "buy", 10)        # off-allowlist never broadcasts


def test_live_rejects_garbage_txhash(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TWAK_WALLET_ADDRESS", "0xabc")
    twak._reset_dry_run()
    monkeypatch.setattr(twak, "_run", lambda args: "Error: insufficient balance")
    with pytest.raises(RuntimeError):
        twak.execute_trade("CAKE", "buy", 10)             # non-hash output is not a confirmed trade


def test_live_accepts_valid_txhash(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TWAK_WALLET_ADDRESS", "0xabc")
    twak._reset_dry_run()
    h = "0x" + "a" * 64
    captured = {}
    def fake_run(args):
        captured["args"] = args
        return '{"txHash": "%s"}' % h
    monkeypatch.setattr(twak, "_run", fake_run)
    assert twak.execute_trade("CAKE", "buy", 10) == h
    # twak resolves by contract address and sizes in USD
    assert captured["args"][1].startswith("0x")          # from = USDT address
    assert captured["args"][2].startswith("0x")          # to = CAKE address
    assert "--usd" in captured["args"]


def test_register_dry_run_simulated():
    assert twak.register().startswith("0xDRYRUN")


def test_balance_empty_in_dry_run():
    assert twak.get_balance() == {}


def test_x402_dry_run_true():
    assert twak.pay_x402("https://example/x402") is True


def test_dry_run_default_is_true(monkeypatch):
    monkeypatch.delenv("DRY_RUN", raising=False)
    twak._reset_dry_run()
    assert twak._dry_run() is True            # safe default: no accidental real trades


def test_dry_run_off_only_for_explicit_false(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    twak._reset_dry_run()
    assert twak._dry_run() is False
    monkeypatch.setenv("DRY_RUN", "0")
    twak._reset_dry_run()
    assert twak._dry_run() is False
