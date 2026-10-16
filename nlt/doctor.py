"""doctor — is everything wired up?"""
from __future__ import annotations

import shutil
import subprocess
import sys

from . import __version__, fishconf
from .brain import chain_report
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

    models = None
    try:
        from .ollama import ping
        models = ping(timeout=1.0)
    except Exception:
        models = None
    rows.append(("ollama (tier 1)", "up · " + ", ".join(models) if models
                 else "not running — optional, not required", True))

    rows.append(("fish integration", fishconf.status_line(), True))

    say()
    for name, val, fine in rows:
        icon = OK("✓") if fine else BAD("✗")
        say(f"  {icon} {paint(f'{name:<17}', '1')} {MUTE(str(val))}")

    say()
    say(GLOW("brain chain (best available wins):"))
    say(paint(chain_report(), "2"))

    if not fish:
        say()
        say(WARN("→ fish-first design; other shells get `nlt '<task>'` only"))
    say()
    return 0
