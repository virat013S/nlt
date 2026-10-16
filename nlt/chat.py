"""Chat mode: a loop. You say what you want; nlt does it. On failure it asks
what happened — type what you saw, or 'diag' and it reads the output itself."""
from __future__ import annotations

import os

from .style import GLOW, MUTE, say
from .task import do_task


def chat(persona, model: str | None, *, dry: bool = False, assume_yes: bool = False,
         no_ai: bool = False) -> int:
    say()
    say(GLOW(f"{persona.icon} {persona.g()}"))
    say(MUTE("leave: 'exit', 'q', Ctrl-D · on failure: free text, or 'diag'"))
    n = 0
    while True:
        say()
        try:
            task = input(f"{persona.icon}>> ").strip()
        except (EOFError, KeyboardInterrupt):
            say()
            break
        if not task:
            continue
        if task.lower() in ("exit", "q", "quit", "nvm"):
            break
        n += 1
        do_task(task, persona, model, dry=dry, assume_yes=assume_yes, cwd=os.getcwd(),
                no_ai=no_ai)
    say()
    say(MUTE(f"chat ended — {n} task(s). bye 👋"))
    return 0
