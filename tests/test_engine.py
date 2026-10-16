"""Engine tests. pty machinery is POSIX-only by nature; everything else is
tested cross-platform (the refusal guard works everywhere)."""
from __future__ import annotations

import os

import pytest

from nlt.engine import run_live, fish_path

POSIX = os.name == "posix"


def test_refuses_interactive_bare():
    r = run_live("fish")  # would wait on us forever — must be refused, anywhere
    assert r.refused is True
    assert r.status == -3


def test_cross_platform_exit():
    r = run_live("python --version")
    assert r.status == 0


@pytest.mark.skipif(not POSIX, reason="pty = posix")
def test_true_and_false():
    assert run_live("true").status == 0
    assert run_live("false").status == 1


@pytest.mark.skipif(not POSIX, reason="pty = posix")
def test_capture_tail():
    r = run_live("echo pony express")
    assert r.status == 0
    assert "pony" in r.tail


@pytest.mark.skipif(not POSIX, reason="pty = posix")
def test_headless_watchdog_kills_silence():
    r = run_live("sleep 120", silence_timeout=0.5)
    assert r.status == -2  # watchdog, not a 120s wait


@pytest.mark.skipif(not POSIX, reason="fish test")
def test_fish_syntax_runs_in_fish():
    if not fish_path():
        pytest.skip("no fish here")
    r = run_live("begin; echo litany; end")
    assert r.status == 0
    assert "litany" in r.tail
