"""Engine tests — the pty runner lives or dies by honesty."""
from __future__ import annotations

import pytest

from nlt.engine import run_live, fish_path


def test_true_and_false():
    assert run_live("true").status == 0
    assert run_live("false").status == 1


def test_capture_tail():
    r = run_live("echo pony express")
    assert r.status == 0
    assert "pony" in r.tail


def test_refuses_interactive_bare():
    r = run_live("fish")  # would wait on us forever — must be refused
    assert r.refused is True
    assert r.status == -3


def test_headless_watchdog_kills_silence():
    r = run_live("sleep 120", silence_timeout=0.5)
    assert r.status == -2  # watchdog, not a 120s wait


def test_fish_syntax_runs_in_fish():
    if not fish_path():
        pytest.skip("no fish here")
    r = run_live("begin; echo litany; end")
    assert r.status == 0
    assert "litany" in r.tail
