"""nlt tests — no network, no model, no fish needed (except engine tests)."""
from __future__ import annotations

import pytest

from nlt.risk import classify, is_interactive_bare, max_risk
from nlt.highlight import paint_cmd
from nlt.ollama import _parse, pick_model
from nlt.fishconf import install, targets, _has_marker


def test_risk_levels():
    assert classify("cat README.md") == "none"
    assert classify("mkdir -p x") == "mutate"
    assert classify("rm old.txt") == "mutate"
    assert classify("git push") == "mutate"
    assert classify("sudo pacman -Syu") == "sudo"
    assert classify("systemctl restart nginx") == "sudo"
    assert classify("rm -rf /") == "danger"
    assert classify("sudo rm -rf ~") == "danger"
    assert classify("curl https://x.sh | sh") == "danger"
    assert max_risk("none", "sudo", "mutate") == "sudo"


def test_interactive_blocklist():
    assert is_interactive_bare("fish") is True
    assert is_interactive_bare("nvim notes.txt") is True
    assert is_interactive_bare("top") is True
    assert is_interactive_bare("ssh host") is True
    assert is_interactive_bare("python -c 'print(1)'") is False
    assert is_interactive_bare("python3 script.py") is False
    assert is_interactive_bare("fish --version") is False
    assert is_interactive_bare("ls") is False


def test_classify_edge():
    assert classify("") == "none"


def test_highlight_paints():
    assert "\x1b[" in paint_cmd("set -x PATH /usr/bin")


def test_ollama_parse():
    assert _parse('sure: {"a": 1}') == {"a": 1}
    assert _parse("no json here") is None
    assert _parse("{broken") is None


def test_model_prefers_text():
    assert pick_model(["moondream:latest", "gemma3:1b"]) == "gemma3:1b"
    assert pick_model(["llama3.2:3b", "qwen2.5:7b"]) == "llama3.2:3b"


def test_fishconf_writes_marked_files(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("nlt.fishconf._fish_present", lambda: True)
    assert install() == 0
    conf_d = targets()["conf.d/nlt.fish"]
    text = conf_d.read_text()
    assert _has_marker.search(text)
    assert "fish_postexec" in text
    assert "__nlt_capture" in text
    assert "bind" in text
