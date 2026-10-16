"""Fish shell citizenship: failure capture, ctrl-g rescue, completions.

Installed files carry a marker so uninstall is surgical.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from . import MARKER, style

CONF_D = """# {marker} (safe to delete anytime)
# watches your commands when they fail — ctrl-g asks nlt what went wrong

function __nlt_capture --on-event fish_postexec
    if test -n "$argv[1]"; and not string match -q "nlt*" "$argv[1]"
        set -l dir (test -n "$XDG_STATE_HOME"; and echo "$XDG_STATE_HOME"; or echo "$HOME/.local/state")/nlt
        test -d "$dir"; or mkdir -p "$dir"
        printf 'cmd=%s\\nstatus=%s\\npid=%s\\ncwd=%s\\n' \\
            "$argv[1]" "$status" "$fish_pid" "$PWD" \\
            > "$dir/last-$fish_pid.state"
    end
end

function __nlt_rescue_last
    # diagnosis + chatter go to the terminal; the confirmed fix command alone
    # comes back on stdout — fish itself evals it, so it runs IN this session,
    # lands in history, and sudo asks for the password the normal way.
    set -l fix (command nlt rescue-last --print-only 2>/dev/null; or echo)
    set fix (string trim -- "$fix")
    if test -n "$fix"
        eval "$fix"
    end
end

if status is-interactive
    bind \\cg __nlt_rescue_last
    bind \\eh __nlt_rescue_last
end
{marker}
""".format(marker=MARKER)

COMPLETIONS = """# {marker} (safe to delete anytime)
complete -c nlt -f
complete -c nlt -n '__fish_use_subcommand' -x -a 'chat'        -d 'talk: tasks until you leave'
complete -c nlt -n '__fish_use_subcommand' -x -a 'rescue-last' -d 'diagnose the last failure'
complete -c nlt -n '__fish_use_subcommand' -x -a 'doctor'      -d 'check ollama/fish/wiring'
complete -c nlt -n '__fish_use_subcommand' -x -a 'model'       -d 'model status / pull a bigger brain'
complete -c nlt -n '__fish_use_subcommand' -x -a 'history'     -d 'recent tasks and fixes'
complete -c nlt -n '__fish_use_subcommand' -x -a 'fish'        -d 'install/uninstall integration'
complete -c nlt -l persona   -x -a 'guide\\tfriendly default brisk\\tfour words max bard\\tepic narration'
complete -c nlt -l model     -x -d 'ollama model override'
complete -c nlt -l no-ai     -d 'skip the model'
complete -c nlt -l dry-run   -d 'print commands, execute nothing'
complete -c nlt -l yes       -d 'skip run confirmations'
{marker}
""".format(marker=MARKER)


def fish_root() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg).expanduser() if xdg else Path.home() / ".config") / "fish"


_has_marker = re.compile(re.escape(MARKER))


def targets() -> dict[str, Path]:
    root = fish_root()
    return {
        "conf.d/nlt.fish": root / "conf.d" / "nlt.fish",
        "completions/nlt.fish": root / "completions" / "nlt.fish",
    }


def _fish_present() -> bool:
    return shutil.which("fish") is not None


def get_source(rel: str) -> str:
    if rel == "conf.d/nlt.fish":
        return CONF_D
    if rel == "completions/nlt.fish":
        return COMPLETIONS
    raise KeyError(rel)


def install() -> int:
    if not _fish_present():
        style.say(style.WARN(
            "no fish on this box — integration skipped (nlt still works standalone: `nlt '<task>'`)"))
        return 1
    written = []
    for rel, dst in targets().items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(get_source(rel), encoding="utf-8")
        written.append(str(dst))
    style.say(style.OK(f"fish wired: {', '.join(written)}"))
    style.say(style.MUTE("reload with: exec fish"))
    style.say(style.MUTE("then fail a command and press ctrl-g."))
    return 0


def uninstall() -> int:
    removed = []
    for _, path in targets().items():
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            if _has_marker.search(text):
                path.unlink()
                removed.append(str(path))
    if removed:
        style.say(style.OK(f"removed: {', '.join(removed)}"))
    else:
        style.say(style.MUTE("nothing found — nothing removed."))
    return 0


def status_line() -> str:
    ok = [rel for rel, path in targets().items()
          if path.exists() and _has_marker.search(path.read_text(encoding="utf-8", errors="replace"))]
    return ", ".join(ok) if ok else "not installed (run: nlt fish install)"
