"""Risk classification + the interactive-program blocklist.

Guardrails the model cannot talk its way past.
"""
from __future__ import annotations

import re

DANGER_RX = re.compile(
    r"\bmkfs\b|\bdd\s+[^\n]*\bof=/|\bshred\b|:\(\)\s*\{\s*:"
    r"|curl[^|;]*\|\s*(ba)?sh\b|wget[^|;]*&&\s*(ba)?sh\b"
    r"|rm\s+(-+r|-+rf|-+fr)(\s|$)|rm\s+--recursive\b"
    r"|chmod\s+-R\s+777\s+/(?:\s|$)|>\s*/dev/sd|git\s+push\s+.*--force",
    re.IGNORECASE,
)

MUTATORS = {
    "rm", "mv", "cp", "dd", "mkfs", "truncate", "chown", "chmod", "kill",
    "pkill", "killall", "ln", "git", "pip", "pip3", "npm", "cargo",
    "make", "cmake", "tar", "unzip", "gzip", "sed", "shred", "crontab",
    "mkdir", "touch", "rmdir", "import", "convert",
}

ROOTY = {
    "apt", "apt-get", "pacman", "dnf", "yum", "zypper", "systemctl",
    "mount", "umount", "useradd", "usermod", "groupmod", "passwd",
}

# Programs that open their own UI/REPL/wait-loop. nlt cannot babysit those —
# the human runs them in their own terminal.
INTERACTIVE_APPS = {
    "fish", "bash", "zsh", "sh", "dash", "python", "python3", "node",
    "irb", "ghci", "julia", "sqlite3", "mysql", "psql", "nvim", "vim",
    "vi", "nano", "emacs", "less", "more", "man", "top", "htop", "btop",
    "tmux", "screen", "gdb", "sftp", "ssh", "ssh-add", "passwd", "ftp",
    # "ftp" no longer; keep set tidy
}
INTERACTIVE_APPS.discard("ftp")
SCREEN_TAKERS = {
    "nvim", "vim", "vi", "nano", "emacs", "less", "more", "man", "top",
    "htop", "btop", "tmux", "screen", "ssh", "sftp", "gdb",
}
HELP_FLAGS = {"-h", "--help", "-v", "--version", "-c", "-e", "-q", "-S", "-l"}


# none < mutate < sudo < danger
LEVELS = {"none": 0, "mutate": 1, "sudo": 2, "danger": 3}
LABELS = {
    "none": "read-only",
    "mutate": "mutates things",
    "sudo": "needs sudo",
    "danger": "⚠ DANGEROUS",
}


def classify(cmd: str) -> str:
    cmd = (cmd or "").strip()
    if not cmd:
        return "none"
    if DANGER_RX.search(cmd):
        return "danger"

    toks = cmd.split()
    sudoed = False
    if toks and toks[0] in ("sudo", "doas"):
        sudoed = True
        toks = toks[1:]
    head = (toks[0] if toks else "").rsplit("/", 1)[-1]

    if head in ROOTY:
        return "sudo"
    if head in MUTATORS or ">" in cmd:
        risk = "mutate"
    elif sudoed:
        risk = "sudo"
    else:
        risk = "none"
    return risk


def is_interactive_bare(cmd: str) -> bool:
    """True when the command would open a REPL/editor/pager/session and wait
    forever (e.g. a bare `fish` step dreamt up by a small model)."""
    toks = (cmd or "").strip().split()
    if toks and toks[0] in ("sudo", "doas"):
        toks = toks[1:]
    if not toks:
        return False
    head = toks[0].rsplit("/", 1)[-1]
    if head not in INTERACTIVE_APPS:
        return False
    if head in SCREEN_TAKERS:
        return True  # always takes over the screen
    if len(toks) == 1:
        return True   # bare REPL wait
    if toks[1] in HELP_FLAGS or not toks[1].startswith("-"):
        return False  # `python -c 'x'`, `python script.py`, `fish --version`
    return True


def max_risk(*risks: str) -> str:
    best = "none"
    for r in risks:
        if LEVELS.get(r, 0) > LEVELS[best]:
            best = r
    return best
