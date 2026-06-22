"""Tests for the veto-only LLM confirm layer. No network — the Gemini seam is mocked."""

import pytest

from brain import llm_confirm
from brain.divergence import DivergenceSignal, Setup
from brain.conviction import Conviction


def _div():
    return DivergenceSignal("CAKE", Setup.ACCUMULATION, 125000.0, 0.8, True, True)


def _conv():
    return Conviction("CAKE", "long", 78.0, 0.8, "strong accumulation")


@pytest.fixture(autouse=True)
def enable(monkeypatch):
    monkeypatch.setenv("VERTEX_PROJECT", "proj")
    monkeypatch.setenv("LLM_CONFIRM", "true")


def test_disabled_allows(monkeypatch):
    monkeypatch.delenv("LLM_CONFIRM", raising=False)
    allow, reason = llm_confirm.confirm(_div(), _conv(), None, 0.0, 0)
    assert allow is True and "disabled" in reason


def test_veto_blocks(monkeypatch):
    monkeypatch.setattr(llm_confirm, "_query_gemini",
                        lambda p: {"allow": False, "reason": "sold CAKE 20m ago"})
    allow, reason = llm_confirm.confirm(_div(), _conv(), None, 5.0, 1)
    assert allow is False and "sold" in reason


def test_confirm_allows(monkeypatch):
    monkeypatch.setattr(llm_confirm, "_query_gemini",
                        lambda p: {"allow": True, "reason": "clean entry"})
    allow, _ = llm_confirm.confirm(_div(), _conv(), None, 0.0, 0)
    assert allow is True


def test_fail_open_on_error(monkeypatch):
    def boom(p):
        raise RuntimeError("vertex down")
    monkeypatch.setattr(llm_confirm, "_query_gemini", boom)
    allow, reason = llm_confirm.confirm(_div(), _conv(), None, 0.0, 0)
    assert allow is True and "error" in reason          # outage never halts trading
