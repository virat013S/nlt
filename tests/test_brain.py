"""brain tests — pattern brain + chain selection. No network, no model.

Every chain test pins OLLAMA_HOST at a dead port so nothing real is pinged,
and clears cloud key envs so the pattern floor is deterministic.
"""
from __future__ import annotations

import pytest

from nlt import brain
from nlt.task import translate, _normalize
from nlt.explain import Context, diagnose


@pytest.fixture(autouse=True)
def _dead_air(monkeypatch):
    """No ollama, no cloud keys, no chatter — pattern brain only."""
    monkeypatch.setattr("nlt.ollama.BASE", "http://127.0.0.1:9")
    monkeypatch.delenv("NLT_MODEL", raising=False)
    for k in ("OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
              "TOGETHER_API_KEY", "NLT_OPENAI_BASE", "NLT_OPENAI_MODEL"):
        monkeypatch.delenv(k, raising=False)


# ------------------------------------------------------------- pattern brain

def test_mkdir_variants():
    for s in ("make a folder called rex", "create the build dir",
              "make a new directory for logs"):
        steps, note = brain.pattern_tasks(s)
        assert steps, f"no plan for {s!r}"
        assert steps[0]["cmd"].startswith("mkdir -p "), (s, steps[0])
    assert brain.pattern_tasks("make a new directory for logs")[0][0]["cmd"] \
        == "mkdir -p logs"


def test_make_file_with_content():
    steps, _ = brain.pattern_tasks("write a file called todo.txt with buy milk")
    assert steps[0]["cmd"] == 'echo "buy milk" > todo.txt'
    steps2, _ = brain.pattern_tasks("create a file in /tmp with hello world notes")
    assert '/tmp/note.txt' in steps2[0]["cmd"]


def test_copy_and_move():
    steps, _ = brain.pattern_tasks("copy a.txt to backup/")
    assert steps[0]["cmd"] == 'cp -rv "a.txt" "backup/"'
    steps2, _ = brain.pattern_tasks("move old.cfg to archive/")
    assert "mv \"old.cfg\" \"archive/\"" in steps2[0]["cmd"]
    assert 'test -e "archive/"' in steps2[0]["cmd"]  # never overwrites silently


def test_delete_is_gated_and_never_bulk():
    steps, _ = brain.pattern_tasks("remove the cache dir")
    assert steps[0]["cmd"].startswith("rm -i "), steps
    assert brain.pattern_tasks("delete everything in downloads")[0] == []


def test_read_list_find():
    assert brain.pattern_tasks("list the files in src")[0][0]["cmd"] == "ls -lah src"
    steps, _ = brain.pattern_tasks("find jpg files in downloads")
    assert "-name '*.jpg'" in steps[0]["cmd"]
    steps2, _ = brain.pattern_tasks("find files named config in etc")
    assert "-iname '*config*'" in steps2[0]["cmd"]


def test_installs_stay_native():
    steps, _ = brain.pattern_tasks("pipx install cowsay")
    assert steps[0]["cmd"] == "pipx install cowsay"
    steps2, _ = brain.pattern_tasks("apt install fzf")
    assert steps2[0]["cmd"] == "sudo apt install fzf"


def test_unknown_sentence_hints_and_never_guesses():
    steps, note = brain.pattern_tasks("do a cartwheel on the moon")
    assert steps == []
    assert "pattern brain" in note


def test_pattern_steps_survive_normalize():
    plan = brain.pattern_tasks("make a folder called rex")
    blob = {"steps": [{"cmd": c["cmd"], "why": c["why"]} for c in plan[0]],
            "note": plan[1]}
    out = _normalize(blob)
    assert out["steps"][0]["cmd"] == "mkdir -p rex"
    assert out["steps"][0]["risk"] == "mutate"  # risk classifier still applies


# --------------------------------------------------------------------- chain

def test_chain_report_mentions_all_tiers():
    rep = brain.chain_report()
    assert "ollama" in rep and "pattern brain" in rep
    assert "not required" in rep or "no key" in rep


def test_active_brain_pattern_floor(monkeypatch):
    kind, model = brain.active_brain()
    assert kind == "pattern"
    assert model is None


def test_active_brain_no_ai_forces_pattern(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    kind, _ = brain.active_brain(no_ai=True)
    assert kind == "pattern"


def test_chat_prefers_pattern_when_nothing_available():
    out, label = brain.chat("sys", "user")
    assert out is None
    assert "pattern" in label


def test_cloud_config_priority(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    cfg = brain.cloud_config()
    assert cfg["env"] == "GROQ_API_KEY"
    assert cfg["base"] == "https://api.groq.com/openai/v1"
    monkeypatch.setenv("NLT_OPENAI_MODEL", "llama-3.3-70b")
    assert brain.cloud_config()["model"] == "llama-3.3-70b"


def test_cloud_chat_failure_returns_none():
    """Dead port → None, and the chain falls onward — no crash, no hang."""
    cfg = {"model": "x", "base": "http://127.0.0.1:9", "key": "k"}
    assert brain._cloud_chat(cfg, "sys", "user") is None


# ------------------------------------------------ translate / rescue wiring

def test_translate_falls_to_pattern(monkeypatch):
    p = translate("make a folder called rex", _stub_persona(), None,
                  cwd="/tmp", no_ai=True)
    assert p["steps"][0]["cmd"] == "mkdir -p rex"
    assert "pattern" in p["note"] or p["steps"]


def test_rescue_diagnose_pattern_127(monkeypatch):
    ctx = Context(command="hamster --netwebs", status=127, cwd="/tmp")
    v = diagnose(ctx, _stub_persona(), None, no_ai=True)
    assert "hamster" in v["cause"]
    assert "which" in v["fix"]


def test_rescue_diagnose_pattern_path(monkeypatch):
    ctx = Context(command="cat /no/such/file.txt", status=2, cwd="/tmp")
    v = diagnose(ctx, _stub_persona(), None, no_ai=True)
    assert "test -e /no/such/file.txt" in v["fix"]


def _stub_persona():
    from types import SimpleNamespace
    return SimpleNamespace(system="you are an assistant", icon="✦")
