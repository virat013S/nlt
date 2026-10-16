"""Terminal style + the one reliable way to talk to a TTY (even from inside
a fish command substitution, where stdin/stdout have been stolen by $(...))."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from . import APP

# ------------------------------------------------ colors

_ENABLE = None


def colors_on() -> bool:
    global _ENABLE
    if _ENABLE is None:
        if os.name == "nt":
            try:
                os.system("")
            except Exception:
                pass
        if os.environ.get("NO_COLOR"):
            _ENABLE = False
        elif os.environ.get("TERM") == "dumb":
            _ENABLE = False
        else:
            _ENABLE = True
    return _ENABLE


def paint(text: object, *codes: str) -> str:
    if not colors_on() or not codes:
        return str(text)
    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"


RESET, DIM, BOLD = "0", "2", "1"
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = "31", "32", "33", "34", "35", "36", "97"

GLOW = lambda s: paint(s, CYAN, BOLD)
BAD = lambda s: paint(s, RED)
WARN = lambda s: paint(s, YELLOW)
OK = lambda s: paint(s, GREEN)
MUTE = lambda s: paint(s, DIM)


# ------------------------------------------------ tty io

_tty_in = None
_tty_out = None


def tty():
    """Explicit terminal handles: fish command substitution leaves us with a
    null stdin and a captured stdout, but /dev/tty is always ours."""
    global _tty_in, _tty_out
    if _tty_in is None:
        try:
            _tty_in = sys.stdin if sys.stdin.isatty() else open("/dev/tty", "r")  # noqa: SIM115
        except Exception:
            _tty_in = None
    if _tty_out is None:
        try:
            _tty_out = sys.stdout if sys.stdout.isatty() else open("/dev/tty", "w")  # noqa: SIM115
        except Exception:
            _tty_out = None
    return _tty_in, _tty_out


def say(*parts: object) -> None:
    """Visible chatter — to the terminal, never into a $( ) capture."""
    _, out = tty()
    print(*parts, file=out or sys.stderr, flush=True)


def ask(question: str, *, choices: str = "yn", default: str) -> str:
    _in, out = tty()
    if not _in:
        return default
    hint = f" [{'/'.join(c.upper() if c == default else c.lower() for c in choices)}]"
    stream = out or sys.stderr
    try:
        stream.write(paint(f"{question}{hint}? ", WHITE))
        stream.flush()
        line = _in.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        stream.write("\n")
        return default
    return line[0] if line and line[0] in choices else default


def ask_text(question: str, *, default: str = "") -> str:
    _in, out = tty()
    if not _in:
        return default
    stream = out or sys.stderr
    try:
        stream.write(paint(f"{question} ", WHITE))
        stream.flush()
        v = _in.readline().strip()
        return v or default
    except (EOFError, KeyboardInterrupt):
        stream.write("\n")
        return default


# ------------------------------------------------ app dirs + history

def root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / APP


def ensure_dirs() -> Path:
    r = root()
    r.mkdir(parents=True, exist_ok=True)
    return r


def log_history(**entry) -> None:
    entry.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    try:
        with open(root() / "history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass
