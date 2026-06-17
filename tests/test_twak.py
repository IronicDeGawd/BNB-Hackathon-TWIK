"""Tests for the TWAK wrapper — dry-run path only (no real broadcasts, no subprocess)."""

import os

import pytest

from execution import twak


@pytest.fixture(autouse=True)
def force_dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")


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


def test_register_dry_run_simulated():
    assert twak.register().startswith("0xDRYRUN")


def test_balance_empty_in_dry_run():
    assert twak.get_balance() == {}


def test_x402_dry_run_true():
    assert twak.pay_x402("https://example/x402") is True


def test_dry_run_default_is_true(monkeypatch):
    monkeypatch.delenv("DRY_RUN", raising=False)
    assert twak._dry_run() is True            # safe default: no accidental real trades


def test_dry_run_off_only_for_explicit_false(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    assert twak._dry_run() is False
    monkeypatch.setenv("DRY_RUN", "0")
    assert twak._dry_run() is False
