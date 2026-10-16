"""Diagnosis: something failed. nlt asks what's wrong — or reads the tail."""
from __future__ import annotations

import os
from dataclasses import dataclass

from . import engine, risk, style
from .brain import chat as brain_chat
from .brain import pattern_rescue
from .highlight import paint_cmd
from .risk import is_interactive_bare
from .speak import Persona
from .style import (
    BAD, GLOW, MUTE, OK, WARN, ask, ask_text, say, tty,
)

MAX_ROUNDS = 4


@dataclass
class Context:
    command: str
    status: int
    cwd: str = ""
    tail: str | None = None
    user_note: str = ""


SCHEMA = (
    'Return ONLY JSON exactly like:\n'
    '{"cause": "one short line naming the problem",'
    ' "why": "one more sentence, plain english",'
    ' "fix": "a single fish shell command that resolves it, or "" if unsure",'
    ' "risk": "none|mutate|sudo|danger"}\n'
    "Rules: fish 4.x syntax only. Never propose bare interactive programs "
    "(fish, bash, nvim, top, ssh...) — they would wait on a tty forever. "
    "When the output tail says '(not captured)', be conservative: prefer an "
    "investigating command (test, ls, cat, which) over a mutating one, and "
    "never diagnose permissions you did not see. If the failure plainly looks "
    "like a permissions problem, prefix the fix with sudo. Never invent files "
    "that were never mentioned. When unsure, return fix:\"\" and explain."
)


def _system(persona: Persona) -> str:
    return persona.system + "\n\n" + SCHEMA


def diagnose(ctx: Context, persona: Persona, model: str | None, *,
             no_ai: bool = False) -> dict:
    user = (
        f"shell: fish\n"
        f"cwd: {ctx.cwd or os.getcwd()}\n"
        f"command that failed: {ctx.command}\n"
        f"exit status: {ctx.status}\n"
        f"output tail: {(ctx.tail or '(not captured)')[:800]}\n"
    )
    if not ctx.tail and not ctx.user_note:
        user += (
            "Note: the real error output is unavailable. Do NOT invent a cause "
            "(do not claim permissions, ownership, or missing files you did not "
            "see). Return either an investigating, read-only look (e.g. test -e "
            "/ ls -ld / which on the mentioned path) or fix:\"\".\n"
        )
    if ctx.user_note:
        user += f"the human says: {ctx.user_note}\n"
    blob, label = brain_chat(_system(persona), user, preferred=model, no_ai=no_ai)
    if blob is None:
        say(MUTE(f"(brain: {label})"))
        blob = pattern_rescue(ctx) or {}
    out = {
        "cause": str(blob.get("cause", "")).strip(),
        "why": str(blob.get("why", "")).strip(),
        "fix": str(blob.get("fix", "")).strip(),
        "risk": str(blob.get("risk", "")).strip().lower(),
    }
    if out["fix"]:
        if is_interactive_bare(out["fix"]):
            out["fix"] = ""  # never run an app that waits on a tty
        else:
            r = out["risk"] if out["risk"] in risk.LEVELS else "none"
            out["risk"] = risk.max_risk(r, risk.classify(out["fix"]))
    return out


def render_verdict(v: dict) -> None:
    say()
    say(GLOW("✦"), GLOW(v.get("cause") or "the cause is unclear"))
    if v.get("why"):
        say(style.MUTE(v["why"]))
    fix = v.get("fix") or ""
    if fix:
        lvl = v.get("risk", "none")
        tag = {"none": OK, "mutate": WARN, "sudo": BAD, "danger": BAD}[lvl](
            f"[{risk.LABELS[lvl]}]")
        say()
        say(style.paint("    → ", "2"), paint_cmd(fix), " ", tag)
    else:
        say(MUTE("    (no fix suggested — nlt doesn't guess at paths)"))


def confirm_fix(v: dict, *, dry: bool = False, assume_yes: bool = False) -> tuple[str, str]:
    """Returns (action, fix). action: run | preview | abort."""
    fix = v.get("fix") or ""
    if not fix:
        return ("abort", "")
    if dry:
        say(WARN(f"    — dry-run: would run: {fix}"))
        return ("preview", fix)
    if v.get("risk", "none") == "danger":
        word = ask_text(BAD(f"type yes to run: {fix}"), default="no")
        if word.strip().lower() != "yes":
            say(MUTE("stayed safe. (not run)"))
            return ("abort", "")
        return ("run", fix)
    if assume_yes:
        return ("run", fix)
    _in, _ = tty()
    if not _in:  # headless, no explicit blessing — show, don't act
        return ("preview", fix)
    r = ask("run this fix", choices="rn", default="n")
    if r == "r":
        return ("run", fix)
    say(MUTE("aborted."))
    return ("abort", "")


def rescue_flow(ctx: Context, persona: Persona, model: str | None, *, dry: bool = False,
                assume_yes: bool = False, print_only: bool = False,
                no_ai: bool = False) -> int:
    """Diagnose → sign-off → execute. print_only: emit the confirmed fix on
    stdout verbatim — fish's ctrl-g evals it in your real session.
    Returns the final known status."""
    v = diagnose(ctx, persona, model, no_ai=no_ai)
    render_verdict(v)
    action, fix = confirm_fix(v, dry=dry, assume_yes=assume_yes)

    if action == "abort" or not fix:
        return ctx.status

    if action == "preview":
        say(MUTE("(shown — not run. pass --yes to act, or bless it when asked.)"))
        return ctx.status

    if print_only:
        print(fix)  # protocol line — fish evals THIS, in-session
        return 0

    res = engine.run_live(fix, cwd=ctx.cwd or None)
    style.log_history(mode="rescue", cmd=fix, cwd=ctx.cwd, exit=res.status)
    say()
    if res.status == 0:
        say(OK(persona.ok()))
        return 0

    # not fixed — nlt asks the human what happened, up to N rounds
    say(BAD(persona.no()), f"(status {res.status})")
    for _ in range(MAX_ROUNDS):
        say()
        say(persona.ask())
        note = ask_text("    >")
        if note.lower() in ("exit", "quit", "q", "nvm", "skip"):
            say(MUTE("ok, stopping here."))
            return res.status
        if note.lower() == "diag" or not note:
            note = ""
        else:
            ctx.user_note = note
        sub = Context(command=fix, status=res.status, cwd=ctx.cwd, tail=res.tail,
                      user_note=ctx.user_note if not note else "")
        v = diagnose(sub, persona, model, no_ai=no_ai)
        render_verdict(v)
        action, fix = confirm_fix(v, dry=False, assume_yes=assume_yes)
        if action != "run" or not fix:
            return res.status
        res = engine.run_live(fix, cwd=ctx.cwd or None)
        style.log_history(mode="rescue", cmd=fix, cwd=ctx.cwd, exit=res.status)
        if res.status == 0:
            say()
            say(OK(persona.ok()))
            return 0
        say()
        say(BAD(persona.no()), f"(status {res.status})")
    say(MUTE("nlt has tried its ideas — over to you, human."))
    return res.status
