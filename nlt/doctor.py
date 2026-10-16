"""doctor — is everything wired up?"""
from __future__ import annotations

import shutil
import subprocess
import sys

from . import __version__, fishconf, ollama
from .style import BAD, GLOW, MUTE, OK, WARN, paint, say


def run() -> int:
    say()
    say(GLOW(f"✦ nlt {__version__} — environment check"))
    rows = []

    rows.append(("python", f"{sys.version_info.major}.{sys.version_info.minor}",
                 sys.version_info >= (3, 9)))

    fish = shutil.which("fish")
    vers = ""
    if fish:
        try:
            vers = subprocess.run([fish, "--version"], capture_output=True,
                                  text=True, timeout=5).stdout.strip().split()[-1]
        except Exception:
            vers = "?"
    rows.append(("fish shell", f"{fish} ({vers})" if fish
                 else "not found — nlt works standalone, just less integrated", bool(fish)))

    models = ollama.ping()
    if models:
        model = ollama.pick_model(models)
        rows.append(("ollama", "up · " + ", ".join(models), True))
        rows.append(("default brain", model or "—", bool(model)))
    else:
        rows.append(("ollama", "not reachable — `ollama serve` or install (ollama.com)", False))

    rows.append(("fish integration", fishconf.status_line(), True))

    say()
    for name, val, fine in rows:
        icon = OK("✓") if fine else BAD("✗")
        say(f"  {icon} {paint(f'{name:<17}', '1')} {MUTE(str(val))}")

    if not models:
        say()
        say(WARN("→ bring a brain: `ollama pull gemma3:1b` (tiny) or `nlt model pull gemma3:4b` (better)"))
    if not fish:
        say()
        say(WARN("→ fish-first design; other shells get `nlt '<task>'` only"))
    say()
    return 0
