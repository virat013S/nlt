"""A tiny fish-aware command painter — nlt colors commands the way fish would."""
from __future__ import annotations

from .style import BAD, DIM, GLOW, OK, WARN, paint

FISH_BUILTINS = {
    "set", "if", "while", "for", "function", "begin", "end", "echo", "test",
    "bind", "abbr", "read", "source", "eval", "status", "math", "string",
    "printf", "cd", "pwd", "exit", "return", "switch", "case", "type",
    "command", "builtin", "history", "contains", "count", "argparse",
}
COMMON = {
    "ls", "cat", "grep", "rg", "find", "sed", "awk", "git", "curl", "wget",
    "tar", "zip", "unzip", "kill", "ps", "head", "tail", "touch", "mkdir",
    "cp", "mv", "rm", "chmod", "chown", "sudo", "apt", "apt-get", "pacman",
    "dnf", "systemctl", "python", "python3", "pip", "pip3", "uv", "node",
    "npm", "cargo", "make", "cmake", "fish", "man", "du", "df", "pillow",
}


def _paint_head(tok: str, depth: int) -> str:
    if tok.startswith(("'", '"')):
        return BAD(tok)
    if tok.startswith("$"):
        return GLOW(tok)
    if tok.startswith("-") and len(tok) > 1:
        return WARN(tok)
    if tok.startswith("/"):
        return OK(tok)
    if tok in FISH_BUILTINS:
        return GLOW(tok)
    if tok in COMMON:
        return OK(tok)
    if depth == 0:
        return GLOW(tok)
    return tok


def paint_cmd(cmd: str) -> str:
    out: list[str] = []
    depth = 0  # 0 = head position: first token or right after a separator
    for raw in cmd.split(" "):
        tok, sep = raw, ""
        while tok and tok[-1] in "|;&":
            sep = tok[-1] + sep
            tok = tok[:-1]
        core = _paint_head(tok, depth) if tok else tok
        out.append(core + (paint(sep, DIM) if sep and tok else sep))
        depth = 0 if sep else depth + 1
    return " ".join(out) if out else cmd
