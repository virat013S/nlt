"""Task mode: natural language in, fish commands out, gated by sign-off."""
from __future__ import annotations

import os

from . import engine, risk, style
from .brain import chat as brain_chat
from .brain import passthrough_task, pattern_tasks
from .highlight import paint_cmd
from .risk import is_interactive_bare
from .speak import Persona
from .style import BAD, GLOW, MUTE, OK, WARN, ask_text, say

TASK_SCHEMA = (
    'Return ONLY JSON exactly like:\n'
    '{"steps": [{"cmd": "one fish shell command", "why": "max 8 words",'
    ' "risk": "none|mutate|sudo|danger"}], "note": "one line of commentary"}\n'
    "Rules: fish 4.x syntax. Use `mkdir -p` where a nesting may be missing. "
    "Prefer pwd-relative paths. If elevation is needed, prefix that step with "
    "sudo. 1-3 steps, each runnable separately in order. Never propose bare "
    "interactive programs (fish, bash, nvim, top, ssh...) — they wait on a tty. "
    "Prefer ONE step that fully does the task over several smaller ones."
)


def translate(task: str, persona: Persona, model: str | None, cwd: str, *,
              no_ai: bool = False) -> dict:
    """Best available brain → normalized plan. model=None is fine: the chain
    tries local, then cloud, and the pattern brain is always there."""
    direct = passthrough_task(task)
    if direct is not None:
        blob, label = direct, "passthrough — commands run as typed"
    else:
        system = persona.system + "\n\n" + TASK_SCHEMA
        user = f"shell: fish\ncwd: {cwd or os.getcwd()}\ntask: {task}"
        blob, label = brain_chat(system, user, preferred=model, no_ai=no_ai)
        if blob is None:
            psteps, note = pattern_tasks(task)
            blob = {"steps": psteps, "note": note}
    say(MUTE(f"(brain: {label})"))
    return _normalize(blob)


def _normalize(blob: dict) -> dict:
    steps: list[dict] = []
    seen: set[str] = set()
    dropped = 0
    for s in blob.get("steps", [])[:4]:
        if not isinstance(s, dict):
            continue
        cmd = str(s.get("cmd", "")).strip()
        if not cmd or cmd in seen:
            continue
        if is_interactive_bare(cmd):
            dropped += 1
            continue
        seen.add(cmd)
        r = str(s.get("risk", "none")).strip().lower()
        r = r if r in risk.LEVELS else "none"
        steps.append({"cmd": cmd, "why": str(s.get("why", ""))[:60],
                      "risk": risk.max_risk(r, risk.classify(cmd))})
    if dropped:
        say(WARN(f"    (dropped {dropped} step(s) that would open an interactive session)"))
    return {"steps": steps, "note": str(blob.get("note", "")).strip()}


def render_plan(p: dict, task: str, persona: Persona) -> None:
    say()
    say(GLOW(f"✦ {task}"))
    if p["note"]:
        say(style.MUTE(p["note"]))
    say()
    for i, s in enumerate(p["steps"], 1):
        tag = {"none": OK, "mutate": WARN, "sudo": BAD, "danger": BAD}[
            s["risk"]](f"[{risk.LABELS[s['risk']]}]")
        say(f"   {style.paint(i, '1')}. {paint_cmd(s['cmd'])} {tag}")
        if s["why"]:
            say(f"      {MUTE(s['why'])}")
    say()


def confirm_plan(p: dict, *, dry: bool = False, assume_yes: bool = False) -> str:
    if assume_yes and not dry:
        return "run"
    if dry:
        say(WARN("dry-run — commands will only be shown, never executed."))
        return "run-preview"
    from .style import tty
    _in, _ = tty()
    if not _in:
        return "abort"  # headless without --yes stays safe-shy
    return ask_text("run it? [run/abort]", default="abort")


def run_steps(p: dict, persona: Persona, model: str | None, cwd: str, *,
              assume_yes: bool = False, no_ai: bool = False) -> int:
    from .explain import Context, rescue_flow
    cwd = cwd or os.getcwd()
    for i, s in enumerate(p["steps"]):
        say(MUTE(f"(step {i + 1}: {s['cmd']})"))
        res = engine.run_live(s["cmd"], cwd=cwd)
        style.log_history(mode="task", cmd=s["cmd"], cwd=cwd, exit=res.status)
        if res.status == 0:
            say(OK(f"✓ step {i + 1} clean."))
            continue
        ctx = Context(command=s["cmd"], status=res.status, cwd=cwd, tail=res.tail)
        say()
        say(BAD(persona.no()), f"(step {i + 1}, status {res.status})")
        answer = ask_text(persona.ask(), default="diag")
        if answer.lower() in ("exit", "quit", "q", "nvm", "skip"):
            say(MUTE("ok, stopping here."))
            return res.status
        if answer.lower() not in ("diag", ""):
            ctx.user_note = answer
        final = rescue_flow(ctx, persona, model, assume_yes=assume_yes, no_ai=no_ai)
        if final != 0:
            return final
    say()
    say(OK(persona.ok()), MUTE("— every step done."))
    return 0


def do_task(task: str, persona: Persona, model: str | None, *, dry: bool = False,
            assume_yes: bool = False, cwd: str = "", no_ai: bool = False) -> int:
    plan = translate(task, persona, model, cwd, no_ai=no_ai)
    render_plan(plan, task, persona)
    if not plan["steps"]:
        say(BAD("the plan came back empty — try rephrasing the task."))
        return 2
    mode = confirm_plan(plan, dry=dry, assume_yes=assume_yes)
    if mode in ("abort", "a", "n", ""):
        say(MUTE("ok — nothing executed."))
        return 1
    if mode == "run-preview":
        say(WARN("(headless: plan shown only. rerun with --yes to let nlt act.)"))
        return 0
    return run_steps(plan, persona, model, cwd, assume_yes=assume_yes, no_ai=no_ai)
