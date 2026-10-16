"""rescue-last: what happens on ctrl-g (or typing nlt with no arguments)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from .explain import Context, rescue_flow
from .speak import get as get_persona
from .style import BAD, MUTE, say


def latest_state(prefer_pid: int | None = None) -> dict | None:
    """Newest last-<pid>.state under ~/.local/state/nlt — written by the
    fish hook after every command you run."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif os.uname().sysname == "Darwin":  # type: ignore[attr-defined]
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    d = base / "nlt"
    cand = list(d.glob("last-*.state"))
    if not cand:
        return None

    def m(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    pick = None
    for p in sorted(cand, key=m, reverse=True):
        if prefer_pid and _pid_of(p) == prefer_pid:
            pick = p
            break
    if pick is None:
        pick = max(cand, key=m)
    if time.time() - m(pick) > 86400:  # a day stale → ignore
        return None
    try:
        kv = {}
        for line in pick.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv[k.strip()] = v
        return {"cmd": kv.get("cmd", ""), "status": int(kv.get("status", "0") or 0),
                "cwd": kv.get("cwd", "")}
    except (OSError, ValueError):
        return None


def _pid_of(p: Path) -> int:
    m = p.stem.rsplit("-", 1)[-1]
    return int(m) if m.isdigit() else -1


def run(persona_id: str, model: str, *, no_ai: bool = False, prefer_pid: int | None = None,
        dry: bool = False, print_only: bool = False, assume_yes: bool = False) -> int:
    st = latest_state(prefer_pid)
    if not st or not st["cmd"]:
        say(MUTE("no failed command on record — ctrl-g hears silence."))
        return 0
    if st["status"] == 0:
        say(MUTE(f"last command was healthy ({st['cmd']!r} → 0) — nothing to fix."))
        return 0

    persona = get_persona(persona_id)
    say(MUTE(f"last failure: {st['cmd']!r} → status {st['status']} (cwd {st['cwd'] or '?'})"))
    ctx = Context(command=st["cmd"], status=st["status"], cwd=st["cwd"])
    if no_ai:
        say(BAD("model disabled — diagnosis needs it. drop --no-ai or run `nlt doctor`"))
        return 1
    return rescue_flow(ctx, persona, model, dry=dry, assume_yes=assume_yes,
                       print_only=print_only)
