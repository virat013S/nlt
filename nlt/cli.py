"""nlt — CLI front door. Natural language is a first-class citizen.

    nlt                            last failure? diagnose. nothing failed? ask for a task
    nlt <task>                     natural language → fish commands → sign-off → run
    nlt chat                       keep talking: tasks until you say exit
    nlt fish install|uninstall     wire/unwire the fish integration (ctrl-g + capture)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from . import APP, __version__
from .ollama import ping as model_ping
from .ollama import pick_model
from .speak import get as get_persona
from .style import BAD, GLOW, MUTE, OK, colors_on, ensure_dirs, say


SPECIAL = {"chat", "rescue-last", "doctor", "fish", "model", "brain", "history"}


def main(argv: list[str] | None = None) -> int:
    from .style import paint
    colors_on()
    ensure_dirs()
    raw = list(sys.argv[1:] if argv is None else argv)

    if raw and raw[0] in ("--version", "-V"):
        print(f"nlt {__version__}")
        return 0
    if raw and raw[0] in ("-h", "--help", "help"):
        _help()
        return 0

    if raw and raw[0] in SPECIAL:
        return _special(raw[0], raw[1:])

    opts, task_text = _split_task(raw)
    if not task_text:
        return _boot(opts)
    return _do_task(" ".join(task_text), opts)


def _help() -> None:
    print(f"""✦ {APP} {__version__} — the Natural Language Terminal.

    nlt                            fix the last failure (ctrl-g in fish does this)
    nlt <task, plain english>      translate → show → sign-off → run in-session
    nlt chat                       keep going: tasks until 'exit'
    nlt rescue-last --dry-run      diagnose the last failed command without acting
    nlt fish install               wire ctrl-g rescue + failure capture into fish
    nlt brain                      show which brains are live (local/cloud/pattern)
    nlt model [pull NAME]          ollama-specific: check or pull a bigger model
    nlt doctor                     environment check
    nlt history [-n N]             recent tasks and fixes

brains — in order of power, all optional except the last:
    1. ollama (local)              private, on-disk — only if YOU started it
    2. cloud api                   just export OPENAI_API_KEY / GROQ_API_KEY /
                                   OPENROUTER_API_KEY / TOGETHER_API_KEY — no install
    3. pattern brain (built-in)    English → fish with zero setup, always works

tasks accept:
    --persona guide|brisk|bard     assistant voice (default: guide)
    --model NAME                   pin the local ollama model
    --no-ai                        pattern brain only — no model calls at all
    --dry-run                      show the plan, execute nothing
    --yes                          skip run confirmations (typed 'yes' still wins on danger)

privacy & passwords: everything runs locally. sudo asks for your password on
your real terminal, hand to mouth with sudo itself — nlt never sees it.""")
    _ = paint  # silence lints


def _split_task(raw: list[str]) -> tuple[dict, list[str]]:
    opts: dict = {"persona": "guide", "model": None, "dry": False, "no_ai": False,
                  "yes": False, "print_only": False}
    text: list[str] = []
    i = 0
    while i < len(raw):
        tok = raw[i]
        if tok == "--persona" and i + 1 < len(raw):
            opts["persona"] = raw[i + 1] if raw[i + 1] in ("guide", "brisk", "bard") else "guide"
            i += 2
            continue
        if tok == "--model" and i + 1 < len(raw):
            opts["model"] = raw[i + 1]
            i += 2
            continue
        if tok in ("--dry-run", "-n"):
            opts["dry"] = True
            i += 1
            continue
        if tok == "--no-ai":
            opts["no_ai"] = True
            i += 1
            continue
        if tok == "--yes":
            opts["yes"] = True
            i += 1
            continue
        if tok == "--print-only":
            opts["print_only"] = True
            i += 1
            continue
        text.append(tok)
        i += 1
    return opts, text


def _boot(opts: dict) -> int:
    """No task given: last failure? → rescue. None? → ask for a task."""
    todo = None
    try:
        from .rescue import latest_state
        st = latest_state()
        if st and st["status"] != 0:
            todo = st
    except Exception:
        todo = None

    if todo:
        from .rescue import run as rescue_run
        return rescue_run(opts["persona"], opts["model"], no_ai=opts["no_ai"],
                          dry=opts["dry"], assume_yes=opts["yes"])
    say(GLOW("✦ nothing is broken right now — so, what should we do?"))
    say(MUTE("give me a task: nlt \"<task>\" · or sit down: nlt chat"))
    return 0


def _do_task(task: str, opts: dict) -> int:
    from .task import do_task
    return do_task(task, get_persona(opts["persona"]), opts["model"],
                   dry=opts["dry"], assume_yes=opts["yes"], no_ai=opts["no_ai"])


def _special(cmd: str, rest: list[str]) -> int:
    if cmd == "chat":
        opts, _ = _split_task(rest)
        from .chat import chat as chat_fn
        return chat_fn(get_persona(opts["persona"]), opts["model"],
                       dry=opts["dry"], assume_yes=opts["yes"], no_ai=opts["no_ai"])

    if cmd == "rescue-last":
        opts, _ = _split_task(rest)
        prefer_pid = int(os.environ.get("NLT_SHELL_PID", "0") or 0)
        from .rescue import run as rescue_run
        return rescue_run(opts["persona"], opts["model"], no_ai=opts["no_ai"],
                          prefer_pid=prefer_pid, dry=opts["dry"],
                          print_only=opts["print_only"], assume_yes=opts["yes"])

    if cmd == "doctor":
        from .doctor import run as doc_run
        return doc_run()

    if cmd == "fish":
        from .fishconf import install, uninstall
        verb = rest[0] if rest else "install"
        return uninstall() if verb in ("uninstall", "remove", "rm") else install()

    if cmd == "brain":
        return _brain_cmd()

    if cmd == "model":
        return _model_cmd(rest)

    if cmd == "history":
        n = 10
        if "-n" in rest:
            try:
                n = int(rest[rest.index("-n") + 1])
            except (ValueError, IndexError):
                n = 10
        return _history(n)

    say(BAD(f"unknown command: {cmd} — try `nlt --help`"))
    return 2


def _brain_cmd() -> int:
    from . import brain
    from .style import MUTE as M, paint
    say()
    say(GLOW("✦ the brain chain — best available intelligence, zero required setup."))
    say(paint(brain.chain_report(), "2"))
    say()
    say(M("every tier is optional (except tier 3, which is built in and free):"))
    say(M("· local: `ollama pull gemma3:1b` then start ollama (private)"))
    say(M("· cloud: export OPENAI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY (no install)"))
    say(M("· neither: the pattern brain handles the everyday language — you're set now"))
    say()
    return 0


def _model_cmd(rest: list[str]) -> int:
    if rest and rest[0] == "pull":
        if len(rest) < 2:
            say(BAD("usage: nlt model pull <model>   (e.g. gemma3:4b)"))
            return 2
        say(MUTE(f"pulling {rest[1]} — the brain grows."))
        return subprocess.call(["ollama", "pull", rest[1]])
    models = model_ping()
    if not models:
        say(MUTE("ollama not running — optional. the pattern brain + cloud keys cover the rest."),
            MUTE("(see `nlt brain`)"))
        return 1
    say(OK(f"brains available: {', '.join(models)}"))
    say(f"default pick: {pick_model(models)}")
    return 0


def _history(n: int) -> int:
    from .style import OK, paint, root
    path = root() / "history.jsonl"
    if not path.exists():
        say(MUTE("no history yet — go fail something, and get fixed."))
        return 0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        mark = OK("✓") if e.get("exit") == 0 else BAD("✗")
        say(f"  {mark} {paint(str(e.get('ts', '')), '2')} {str(e.get('mode', '?')):>7} "
            f"{str(e.get('cmd', ''))[:72]}")
    return 0


_ = sys  # noqa: F401  (kept for future direct fds)
