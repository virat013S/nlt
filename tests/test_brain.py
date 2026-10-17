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


# ------------------------------------------------------- passthrough commands

def test_passthrough_runs_commands_as_typed():
    got = brain.passthrough_task("git status")
    assert got and got["steps"][0]["cmd"] == "git status"
    got2 = brain.passthrough_task("echo hello world")
    assert got2 and got2["steps"][0]["cmd"] == "echo hello world"
    got3 = brain.passthrough_task("./build.sh --fast")
    assert got3 and got3["steps"][0]["cmd"] == "./build.sh --fast"
    assert brain.passthrough_task("") is None
    assert brain.passthrough_task("not-a-real-cmd-xyz") is None


def test_passthrough_rejects_sentences():
    for sentence in ("make a folder", "list files", "copy the file to backup",
                     "git push to origin", "build me a website please"):
        assert brain.passthrough_task(sentence) is None, sentence


def test_passthrough_never_grabs_package_verbs():
    # coreutils install exists on PATH, but these heads are English intent
    for sentence in ("install firefoks", "download firefox", "setup git"):
        assert brain.passthrough_task(sentence) is None, sentence


def test_translate_passthrough_skips_brains():
    p = translate("git status", _stub_persona(), None, cwd="/tmp",
                  no_ai=True)
    assert p["steps"][0]["cmd"] == "git status"
    assert "passthrough" in p["note"]


# ------------------------------------------------------------- wider families

def test_pattern_system_families():
    for task, needle in (
        ("how much ram is free", "free -h"),
        ("how much disk space is left", "df -h"),
        ("battery level", "power_supply"),
        ("weather in paris", "wttr.in/paris"),
        ("what is the weather", "wttr.in?format=3"),
        ("kill firefox", "pkill -f firefox"),
        ("restart the ssh service", "systemctl restart ssh"),
        ("show me the latest ssh logs", "journalctl -n 40 --no-pager -u ssh"),
        ("commit everything", "git commit"),
        ("push my changes", "git push"),
        ("make script.sh executable", "chmod +x script.sh"),
        ("search for TODO in files", 'grep -n --max-count=10 -r "TODO"'),
        ("download https://example.com/x.tar.gz",
         "curl -fLO https://example.com/x.tar.gz"),
        ("what is using the most space", "du -sh"),
    ):
        steps, _ = brain.pattern_tasks(task)
        assert any(needle in s["cmd"] for s in steps), (task, steps)


def test_pattern_kill_never_guessed():
    steps, note = brain.pattern_tasks("stop the process")
    assert steps == [] and "process" in note


# ---------------------------------------------------------------- toolbox --

def test_spell_rescue_fixes_the_package():
    from nlt import toolbox
    pkg, note = toolbox.fix("firefoks")
    assert pkg == "firefox" and "firefox" in note
    exact, no_note = toolbox.fix("git")
    assert exact == "git" and no_note == ""


def test_help_cards():
    from nlt import toolbox
    card = toolbox.help_for("how do I use nmap")
    assert card["tool"] == "nmap" and "-sn" in card["quick"]
    assert toolbox.help_for("what is git")["tool"] == "git"
    assert toolbox.help_for("make a folder") is None
    assert toolbox.help_for("what is the weather") is None


def test_suggest_note_ranks_real_names():
    from nlt import toolbox
    note = toolbox.suggest_note("nmaap scan the network")
    assert "nmap" in note and "help with nmap" in note
    assert toolbox.suggest_note("do a cartwheel") == ""
    assert "firefox" in toolbox.suggest_note("how do i open firefoks")


def test_install_typo_becomes_firefox():
    steps, _ = brain.pattern_tasks("install firefoks")
    assert steps and "firefox" in steps[0]["cmd"]
    assert "assumed" in steps[0]["why"]


def test_download_means_install_and_forgives_typos():
    steps, _ = brain.pattern_tasks("download firefox")
    assert steps and steps[0]["cmd"].endswith("firefox")
    assert "pacman -S" in steps[0]["cmd"] or "apt install" in steps[0]["cmd"]
    steps2, _ = brain.pattern_tasks("download firefoks")
    assert steps2 and "firefox" in steps2[0]["cmd"]
    steps3, note3 = brain.pattern_tasks("download the file")
    assert not steps3 and "link" in note3


def test_scan_tasks():
    steps, _ = brain.pattern_tasks("nmap scan my network")
    assert steps and steps[0]["cmd"].startswith("nmap -sn")
    steps2, _ = brain.pattern_tasks("scan for open ports on localhost")
    assert steps2 and steps2[0]["cmd"] == "nmap localhost"


def test_exit_127_suggests_close_names():
    ctx = Context(command="nmaap scan", status=127, cwd="/tmp")
    v = diagnose(ctx, _stub_persona(), None, no_ai=True)
    assert "did you mean" in v["cause"] and "nmap" in v["cause"]


def test_help_flows_through_do_task(capsys):
    from nlt import task as task_mod
    code = task_mod.do_task("help with nmap", _stub_persona(), None,
                            dry=True, assume_yes=True, no_ai=True)
    out = capsys.readouterr().err
    assert code == 0 and "nmap" in out and "docs" in out


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
