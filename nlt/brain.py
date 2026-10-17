"""The brain chain — best available intelligence, zero required setup.

  1. local Ollama  — only if YOU installed + started it (full privacy)
  2. cloud keys    — only if YOU exported OPENAI_API_KEY / GROQ_API_KEY /
                     OPENROUTER_API_KEY / TOGETHER_API_KEY (no install)
  3. pattern brain — always on: deterministic English → fish, zero setup

Nothing requires a download. The pattern brain is the floor, not a toy:
it answers the everyday half of terminal life with plain regexes and hands
anything unfamiliar back to the human with a shrug and a hint.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.request

from . import toolbox
from .ollama import chat_json, pick_model, ping
from .style import MUTE, say


# ================================================================= chain --

def ollama_model() -> str | None:
    models = ping(timeout=1.0)
    return pick_model(models) if models else None


def cloud_config() -> dict | None:
    """First exported cloud key, in priority order. None → no cloud brain."""
    specs = [
        ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini", "openai"),
        ("GROQ_API_KEY", "https://api.groq.com/openai/v1", "llama-3.1-8b-instant", "groq"),
        ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini", "openrouter"),
        ("TOGETHER_API_KEY", "https://api.together.xyz/v1", "meta-llama/Llama-3-8b-chat-hf", "together"),
    ]
    for env, base, model, label in specs:
        key = os.environ.get(env)
        if key:
            return {"env": env,
                    "base": os.environ.get("NLT_OPENAI_BASE") or base,
                    "model": os.environ.get("NLT_OPENAI_MODEL") or model,
                    "label": label, "key": key}
    return None


def active_brain(preferred: str | None = None, *, no_ai: bool = False) -> tuple[str, str | None]:
    """('ollama' | 'cloud' | 'pattern', model-or-None). Never raises."""
    if no_ai:
        return ("pattern", None)
    preferred = preferred or os.environ.get("NLT_MODEL")
    if preferred:
        models = ping(timeout=1.0)
        if models and preferred in models:
            return ("ollama", preferred)
        say(MUTE(f"(model '{preferred}' not reachable — dropping down the chain)"))
    else:
        local = ollama_model()
        if local:
            return ("ollama", local)
    cloud = cloud_config()
    if cloud:
        return ("cloud", cloud["model"])
    return ("pattern", None)


def chat(system: str, user: str, preferred: str | None = None, *,
         no_ai: bool = False, timeout: float = 90.0) -> tuple[dict | None, str]:
    """Ask the best available brain once. Returns (json|None, label).
    Falls down the chain on any hiccup — the pattern net catches everything."""
    if no_ai:
        return None, "pattern brain (zero setup)"
    kind, model = active_brain(preferred)
    if kind == "ollama" and model:
        out = chat_json(model, system, user, timeout=timeout)
        if out is not None:
            return out, f"model: {model} (local)"
        say(MUTE("(the local model hiccoughed — trying the next tier)"))
    cloud = cloud_config()
    if cloud:
        out = _cloud_chat(cloud, system, user)
        if out is not None:
            return out, f"model: {cloud['model']} (cloud)"
        say(MUTE("(no cloud brain answered — pattern brain takes the wheel)"))
    return None, "pattern brain (zero setup)"


def _cloud_chat(cfg: dict, system: str, user: str) -> dict | None:
    """One OpenAI-compatible chat round. json|None."""
    body_obj = {
        "model": cfg["model"],
        "temperature": 0.15,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    body = json.dumps(body_obj).encode()
    req = urllib.request.Request(
        f"{cfg['base']}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['key']}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            content = json.load(r)["choices"][0]["message"]["content"]
    except Exception:
        return None
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return None


def chain_report() -> str:
    local = ollama_model()
    cloud = cloud_config()
    line1 = f"  1. ollama (private, on your disk) : {local or 'not running — optional, not required'}"
    if cloud:
        line2 = f"  2. cloud api (optional)           : {cloud['model']} via {cloud['label']}"
    else:
        line2 = ("  2. cloud api (optional)           : no key exported — fine, not required "
                 "(OPENAI/GROQ/OPENROUTER/TOGETHER_API_KEY)")
    line3 = "  3. pattern brain                  : always on — zero setup, zero downloads"
    return "\n".join([line1, line2, line3])


# ======================================================== the pattern brain ==

PATH_RX = r"(?:~/|/|\./)?[\w./@+~\-]+"

STOPWORDS = frozenset((
    "a", "an", "the", "my", "me", "your", "his", "her", "its", "it",
    "this", "that", "these", "those", "them", "there", "here",
    "and", "or", "in", "on", "into", "of", "for", "to", "from", "with",
    "about", "at", "as", "is", "was", "are", "be", "were",
    "file", "files", "folder", "folders", "directory", "directories", "dir", "dirs",
    "contents", "content", "text", "texts", "word", "words", "line", "lines",
    "name", "named", "called", "everything", "thing", "things", "stuff", "all",
    "read", "show", "open", "view", "display", "says", "saying", "please", "nlt",
    "delete", "remove", "trash", "wipe", "del", "rm", "rmdir",
    "copy", "duplicate", "backup", "move", "rename", "mv", "cp",
    "make", "create", "write", "touch", "build",
    "find", "search", "locate", "install", "setup", "update", "upgrade",
    "zip", "compress", "archive", "tar", "pack", "extract", "unzip", "untar", "unpack",
    "list", "ls", "cat", "edit", "editor", "kill", "pkill", "run", "up", "down",
))

_WHY = {
    "mkdir": "create the directory (nesting-safe)",
    "makefile": "create the file (with content if asked)",
    "cp": "copy the source into place",
    "mv": "move it (refuses to overwrite a live target)",
    "rm": "remove it, asking per-file (-i)",
    "cat": "show the file",
    "ls": "list the folder",
    "find": "hunt by name/type under the folder",
    "install": "install via your package manager",
    "update": "refresh the whole system",
    "zip": "make an archive of it",
    "extract": "pull the archive apart",
    "du": "biggest space hogs, sorted",
    "sys": "the quick who-what-where",
    "net": "reach-check the internet",
    "ports": "what's listening where",
    "edit": "opens in your $EDITOR",
    "grep": "search inside files",
    "tree": "the folder at a glance",
    "git": "git does the thing",
    "download": "pull it down with curl",
    "svc": "systemctl the service",
    "logs": "the latest journal lines",
    "kill": "politely terminate the process",
    "ps": "busiest processes first",
    "mem": "RAM use, human units",
    "df": "free space per filesystem",
    "battery": "charge percentage",
    "weather": "a quick look out the window",
    "chmod": "make it executable",
    "nmap": "network scan — careful on nets that aren't yours",
}

# -- literal-command passthrough: type the command itself, run it as typed --

FILLERS = frozenset((
    "a", "an", "the", "my", "our", "their", "this", "that", "please",
    "can", "could", "would", "will", "should", "shall", "do", "does", "did",
    "is", "are", "was", "were", "you", "me", "it", "i", "we",
    "for", "from", "with", "into", "in", "on", "at", "of", "to", "and", "or",
    "folder", "file", "files", "directory", "show", "list", "tell",
))

BUILTIN_HEADS = frozenset((
    "cd", "echo", "test", "pwd", "and", "or", "not", "if", "else", "end",
    "for", "while", "begin", "function", "return", "switch", "case", "set",
    "alias", "source", "history", "jobs", "bg", "fg", "eval", "exec", "wait",
    "math", "string", "count", "contains", "random", "status", "type", "time",
    "exit", "true", "false", "printf", "read", "argparse", "abbr", "builtin",
))


def passthrough_task(raw: str) -> dict | None:
    """You typed a command, not a sentence — nlt runs it as written.

    The step still passes the normal risk + confirm gates, so rm, git push
    and sudo ask before they touch anything. This is how nlt 'gets every
    command': anything on your PATH, typed exactly, needs no translation."""
    raw = raw.strip()
    if not raw or "\n" in raw or len(raw) > 400:
        return None
    words = raw.split()
    if not words or len(words) > 40:
        return None
    base = words[0].rsplit("/", 1)[-1].lower()
    if base in FILLERS:
        return None
    if base in ("install", "download", "setup"):
        return None  # English package verbs first — the brain turns these into intent
    if (base not in BUILTIN_HEADS and shutil.which(words[0]) is None
            and not words[0].startswith(("./", "/", "~/"))):
        return None
    if any(w.lower() in FILLERS for w in words[1:]):
        return None
    return {"steps": [{"cmd": raw,
                       "why": "typed as-is — your command, no translation"}],
            "note": "passthrough — you gave a command, not a sentence"}


def _first_named_path(t: str) -> str:
    for tok in re.findall(PATH_RX, t):
        if tok.lower() not in STOPWORDS:
            return tok
    return ""


def _dir_of(t: str) -> str:
    m = re.search(
        rf"(?:in|into|inside|under)\s+(?:the\s+)?(?:folder|directory|dir)?\s*({PATH_RX})",
        t, re.IGNORECASE)
    if not m:
        return "."
    val = m.group(1).rstrip("/.,!'\"").lower()
    if val in STOPWORDS:
        return "."
    return val


def _called(t: str) -> str:
    m = re.search(rf"\b(?:called|named)\s+({PATH_RX})", t, re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1).strip("'\"")
    return "" if val.lower() in STOPWORDS else val


def _about(t: str) -> str:
    m = re.search(rf"\b(?:on|about|from|of)\s+(?:the\s+)?({PATH_RX})", t, re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1).rstrip("/.,!'\"")
    return "" if val.lower() in STOPWORDS else val


def _qbody(t: str) -> str:
    m = re.search(r'"([^"]{1,200})"', t)
    if m:
        return m.group(1)
    m = re.search(
        r"(?:saying|reads?|containing|contents?)\s+(?:the\s+)?(?:word|words|text|line)\s+([^.!?\n]{1,120})",
        t, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip("'\"")
    m = re.search(r"\bwith\s+([^.!?\n]{1,120}?)\s*(?:\bnotes?\b|\bfiles?\b|\blogs?\b)?\s*[.!]?\s*$",
                  t, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip("'\"")
    return ""


def _tail_noun(t: str, verb_rx: str) -> str:
    """First real noun after an action verb, skipping filler words."""
    m = re.search(rf"{verb_rx}\s+(?:the\s+|my\s+|all\s+|your\s+)*(?P<rest>.+)$",
                  t, re.IGNORECASE)
    if not m:
        return ""
    for tok in re.findall(PATH_RX, m.group("rest")):
        if tok.lower() not in STOPWORDS:
            return tok.rstrip(".,!'\"")
    return ""


def _pkg_name(t: str) -> str:
    m = re.search(r"\b(?:install|setup)\b\s+(?:the\s+)?(?:package\s+)?([a-zA-Z][\w\-]{1,40})",
                  t, re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1)
    return "" if val.lower() in STOPWORDS else val


def _arch_like() -> bool:
    try:
        return os.path.exists("/etc/pacman.conf")
    except OSError:
        return False


def pattern_tasks(t: str) -> tuple[list[dict], str]:
    """English → fish, deterministically. Returns ([steps], note).
    Every generated step still passes the normal risk + confirm gates."""
    orig = t.strip()
    t = " " + t.strip().lower() + " "
    d = _dir_of(t)
    name = _called(t)
    body = _qbody(t)
    steps: list[dict] = []
    hint = ""

    def add(cmd: str, why: str) -> None:
        if cmd.strip():
            steps.append({"cmd": cmd, "why": why})

    if re.search(r"\b(make|create|add|new)\b.*\b(folder|directory|dir)s?\b", t):
        name = name or _tail_noun(t, r"\bfor\b")
        folder = name or (d if d != "." else "new-folder")
        if d != "." and name:
            add(f"mkdir -p {d}/{name}", _WHY["mkdir"])
        else:
            add(f"mkdir -p {folder}", _WHY["mkdir"])

    elif re.search(r"\b(make|create|add|write|touch)\b.*\b(files?|notes?|log)s?\b", t):
        fname = name or "note.txt"
        rel = f"{d}/{fname}" if d != "." else fname
        if d != ".":
            add(f"mkdir -p {d}; and echo \"{body or 'todo'}\" > {rel}", _WHY["makefile"])
        else:
            add(f"echo \"{body or 'todo'}\" > {fname}", _WHY["makefile"])

    elif re.search(r"\b(executable|chmod|chown)\b", t):
        m = re.search(
            rf"\b(?:make|chmod)\s+(?:the\s+|my\s+)?({PATH_RX})\s+(?:file\s+)?executable",
            t, re.IGNORECASE)
        chmod_tgt = (m.group(1) if m and m.group(1).lower() not in STOPWORDS
                     else _first_named_path(t))
        add(f"chmod +x {chmod_tgt or 'THE-SCRIPT'}", _WHY["chmod"])

    elif re.search(r"\b(grep|inside files?|in files?|file contents|containing)\b", t):
        m = re.search(
            rf"\b(?:grep|search|look)\b(?:\s+for)?\s+(?:the\s+)?({PATH_RX})",
            t, re.IGNORECASE)
        pat = m.group(1) if m and m.group(1).lower() not in STOPWORDS else ""
        if pat:
            cm = re.search(re.escape(pat), orig, re.IGNORECASE)
            if cm:                       # keep the casing you typed
                pat = cm.group(0)
            add(f'grep -n --max-count=10 -r "{pat}" . 2>/dev/null | head -40',
                _WHY["grep"])
        else:
            hint = "search for what? name the text or pattern"

    elif re.search(r"\b(tree|structure)\b", t):
        add("tree -L 2 2>/dev/null; or find . -maxdepth 2 -not -path '*/.*'",
            _WHY["tree"])

    elif re.search(r"\b(commit|push|pull|git)\b", t):
        if re.search(r"\bcommit\b", t):
            add('git add -A; and git commit -m "work in progress"', _WHY["git"])
        elif re.search(r"\bpush\b", t):
            add("git push", _WHY["git"])
        elif re.search(r"\bpull\b", t):
            add("git pull", _WHY["git"])
        else:
            add("git status -sb; and git log --oneline -5", _WHY["git"])

    elif re.search(r"\b(download|wget)\b", t):
        m = re.search(r"\b((?:https?://\S+|[\w.\-]+\.[a-z]{2,}(?:/\S*)?))", t)
        url = m.group(1).rstrip(".,)!") if m else ""
        if url:
            add(f"curl -fLO {url}", _WHY["download"])
        else:
            obj = _tail_noun(t, r"\b(?:download|wget)\b")
            pkg, note = toolbox.fix(obj) if obj else ("", "")
            if pkg and (pkg.lower() in toolbox.pool() or note):
                add(f"sudo {'pacman -S --needed' if _arch_like() else 'apt install'} {pkg}",
                    _WHY["download"]
                    + (" — downloads mean installs here" if not note else note))
            else:
                hint = ("download what? give me the link, "
                        "or name a package to install")

    elif re.search(r"\b(services?|daemons?|systemctl|systemd)\b", t):
        m = re.search(rf"\b({PATH_RX})\s+(?:services?|daemons?|units?)\b", t)
        svc = m.group(1) if m and m.group(1).lower() not in STOPWORDS else ""
        act = re.search(r"\b(start|stop|restart|enable|disable|status)\b", t)
        if act and not svc:
            m2 = re.search(
                rf"\b(?:start|stop|restart|enable|disable|status)\b\s+(?:the\s+)?({PATH_RX})",
                t)
            svc = m2.group(1) if m2 and m2.group(1).lower() not in STOPWORDS else ""
        if act and svc:
            sudo = "" if act.group(1) == "status" else "sudo "
            add(f"{sudo}systemctl {act.group(1)} {svc}", _WHY["svc"])
        else:
            add("systemctl --failed", _WHY["svc"])

    elif re.search(r"\b(logs?|journal)\b", t):
        m = re.search(rf"\b({PATH_RX})\s+logs?\b", t)
        unit = m.group(1) if m and m.group(1).lower() not in STOPWORDS else ""
        add(f"journalctl -n 40 --no-pager{(' -u ' + unit) if unit else ''}",
            _WHY["logs"])

    elif re.search(r"\b(kill|stop|terminate|killall|force quit)\b", t):
        target = _tail_noun(t, r"\b(?:kill|stop|terminate|killall|force quit)\b")
        if target and target not in ("process", "app", "program", "job",
                                     "task", "service", "daemon"):
            add(f"pkill -f {target}", _WHY["kill"])
        else:
            hint = "kill which one? name the process"

    elif re.search(r"\b(processes|ps aux|cpu usage|what'?s running|running processes)\b", t):
        add("ps -eo pid,pcpu,pmem,comm --sort=-pcpu | head -12", _WHY["ps"])

    elif re.search(r"\b(ram|memory)\b", t):
        add("free -h", _WHY["mem"])

    elif re.search(r"\b(how much (space|disk)|space left|disk (free|usage)|how full|\bdf\b)", t):
        add("df -h", _WHY["df"])

    elif re.search(r"\b(battery|charge level|power level)\b", t):
        add("cat /sys/class/power_supply/BAT*/capacity 2>/dev/null; "
            "or echo no-battery", _WHY["battery"])

    elif re.search(r"\b(weather|forecast)\b", t):
        m = re.search(
            rf"\b(?:weather|forecast)\b(?:\s+(?:in|at|for)\s+)?({PATH_RX})", t)
        loc = m.group(1) if m and m.group(1).lower() not in STOPWORDS else ""
        suffix = f"wttr.in/{loc}?format=3" if loc else "wttr.in?format=3"
        add(f'curl -s "{suffix}"', _WHY["weather"])

    elif re.search(r"\b(copy|duplicate|backup)\b", t):
        m = re.search(
            rf"(?:copy|duplicate|backup)\s+(?:the\s+)?({PATH_RX})\s*(?:to|into|in|as)\s+({PATH_RX})",
            t, re.IGNORECASE)
        if m and m.group(1).lower() not in STOPWORDS and m.group(2).lower() not in STOPWORDS:
            add(f"cp -rv \"{m.group(1)}\" \"{m.group(2)}\"", _WHY["cp"])
        elif d != ".":
            add(f"cp -r * {d}/", _WHY["cp"])
        else:
            hint = "copy what, to where? name a source and a destination"

    elif re.search(r"\b(move|rename)\b", t):
        m = re.search(
            rf"(?:move|rename)\s+(?:the\s+)?({PATH_RX})\s*(?:to|into|in|as)\s+({PATH_RX})",
            t, re.IGNORECASE)
        if m and m.group(1).lower() not in STOPWORDS and m.group(2).lower() not in STOPWORDS:
            add(f"test -e \"{m.group(2)}\"; and echo 'target exists — not overwriting'; "
                f"or mv \"{m.group(1)}\" \"{m.group(2)}\"", _WHY["mv"])
        else:
            hint = "move what, to where? name a source and a destination"

    elif re.search(r"\b(delete|remove|trash)\b.*\beverything\b", t) or re.search(r"\bdel\b", t):
        hint = "deleting in bulk is yours to spell: rm <paths>"

    elif re.search(r"\b(delete|remove|trash)\b", t):
        tgt = _tail_noun(t, r"\b(?:delete|remove|trash)\b")
        if tgt:
            add(f"rm -i {tgt}", _WHY["rm"])
        else:
            hint = "delete what? name the exact target — deletions are never guessed"

    elif re.search(r"\bnmap\b", t) or re.search(r"\bscan\b.*\b(ports?|network|hosts?)\b", t):
        if re.search(r"\b(network|lan|the net)\b", t):
            add(f"nmap -sn {toolbox.local_net()}", _WHY["nmap"])
        else:
            host = _about(t)
            if not host or host.lower() in STOPWORDS:
                host = _tail_noun(t, r"\b(?:nmap|scan)\b")
            if host and host.lower() not in ("ports", "port", "host", "hosts"):
                add(f"nmap {host}", _WHY["nmap"])
            else:
                add("nmap localhost", _WHY["nmap"])

    elif re.search(r"\b(open|view|show|read|display|cat)\b", t) \
            and not re.search(r"\b(ports?|listening|nmap)\b", t):
        inner = re.search(rf"\b(?:readme|file|contents)\s*(?:of|in|for)\s+({PATH_RX})", t)
        if inner and inner.group(1).lower() in STOPWORDS:
            inner = None
        tgt = inner.group(1) if inner else (_about(t) or _first_named_path(t))
        add(f"cat {tgt or 'README*'}", _WHY["cat"])

    elif re.search(r"\blist\b.*\b(files|contents|directory|folder)\b", t):
        add(f"ls -lah {d}" if d != "." else "ls -lah", _WHY["ls"])

    elif re.search(r"\b(find|search|locate)\b", t):
        ext_m = re.search(r"\b(?:like\s+(\w{1,12})|\b(\w{1,12})\s+files?\b)", t, re.IGNORECASE)
        ext = (ext_m.group(1) or ext_m.group(2) or "").lower() if ext_m else ""
        if ext in STOPWORDS:
            ext = ""
        needle = (ext
                  or (_tail_noun(t, r"\bnamed\b") if re.search(r"\bnamed\b", t) else "")
                  or _tail_noun(t, r"\b(?:find|search|locate)\b"))
        if needle:
            finding = f"-name '*.{needle}'" if ext else f"-iname '*{needle}*'"
            add(f"find {d} -maxdepth 3 {finding} 2>/dev/null | head -40", _WHY["find"])
        else:
            hint = "find what? give a name or a type, e.g. 'find jpg files in downloads'"

    elif re.search(r"\b(install|setup)\b", t):
        pm = re.search(r"\b(apt(?:-get)?|dnf|zypper|pacman)\b\s+([^.!?\n]*\w)", t, re.IGNORECASE)
        mgr = re.search(r"\b(pip3?|pipx|npm|cargo|uv)\s+(?:install|add)\s+([\w\-./]+)", t)
        if pm:
            add(f"sudo {pm.group(1)} {pm.group(2).rstrip('.,!')}", _WHY["install"])
        elif mgr:
            add(f"{mgr.group(1)} install {mgr.group(2)}", _WHY["install"])
        elif _pkg_name(t):
            pkg, note = toolbox.fix(_pkg_name(t))
            exact = pkg.lower() in toolbox.pool()
            if not exact and not note:
                near = toolbox.suggest(pkg, 2)
                hint = (f"{pkg} isn't a repo package or a command I know"
                        + (f" — did you mean {', '.join(near)}?" if near else ""))
            else:
                add(f"sudo {'pacman -S --needed' if _arch_like() else 'apt install'} {pkg}",
                    _WHY["install"] + (f" — {note}" if note else ""))
        else:
            hint = "install what? name the package"

    elif re.search(r"\b(update|upgrade)\b", t):
        add("sudo pacman -Syu" if _arch_like()
            else "sudo apt update; and sudo apt upgrade", _WHY["update"])

    elif re.search(r"\b(extract|unzip|untar|unpack)\b", t):
        src = _tail_noun(t, r"\b(?:extract|unzip|untar|unpack)\b") or _about(t) or "THE-ARCHIVE"
        add(f"mkdir -p {src}-out; and unzip -o {src} -d {src}-out 2>/dev/null; "
            f"or tar -xf {src} -C {src}-out", _WHY["extract"])

    elif re.search(r"\b(zip|archive|compress|tar|pack up)\b", t):
        src = _tail_noun(t, r"\b(?:zip|archive|compress|tar|pack up)\b") or name
        if src:
            add(f"tar -czf \"{src}.tar.gz\" \"{src}\"", _WHY["zip"])
        else:
            hint = "archive what? name the folder or file to pack up"

    elif re.search(r"\b(size|sizes|disk|space|du|biggest|largest)\b", t):
        add(f"du -sh {d if d != '.' else '.'}/* 2>/dev/null | sort -rh | head -15", _WHY["du"])

    elif re.search(r"\b(ports|listening|netstat)\b", t):
        add("ss -tlnp", _WHY["ports"])

    elif re.search(r"\b(internet|connectivity|ping|online)\b", t):
        add("ping -c 3 1.1.1.1", _WHY["net"])

    elif re.search(r"\b(whoami|what system|system info|what distro|which day|what time|when|date)\b", t):
        add("date; and whoami; and uname -rs; and echo \"$PWD\"", _WHY["sys"])

    elif re.search(r"\b(edit|editor|nano|nvim|vim)\b", t):
        m = re.search(rf"\b(?:editor|edit)\b\s*(?:the\s+)?({PATH_RX})", t, re.IGNORECASE)
        path = m.group(1) if m and m.group(1).lower() not in STOPWORDS else (name or _about(t))
        add(f"$EDITOR {path or 'todo.txt'}", _WHY["edit"])

    if steps:
        return steps, "pattern brain — plain arithmetic, no model"
    if hint:
        return [], hint + toolbox.suggest_note(orig)
    return [], ("the pattern brain didn't recognize that sentence — name things clearly, "
                "or add a brain: see `nlt brain` (ollama optional, cloud key optional, all optional)"
                ) + toolbox.suggest_note(orig)


# ================================================================= rescue ==

def pattern_rescue(ctx) -> dict | None:
    """No-model rescue for well-known failure families. Read-only fixes only."""
    cmd = getattr(ctx, "command", "") or ""
    status = getattr(ctx, "status", 0)
    tokens = cmd.split()
    head = tokens[0] if tokens else "?"

    if status == 127:
        sug = toolbox.suggest(head)
        near = f" — did you mean `{sug[0]}`?" if sug else ""
        return {
            "cause": f"`{head}` is not a command on your PATH{near}",
            "why": ("typo most likely, or not installed — check first; "
                    "nlt won't install anything without you." + (
                        f" `help with {sug[0]}` prints its cheat sheet." if sug else "")),
            "fix": f"which {head}; or echo '{head} is not installed — install it with your package manager'",
            "risk": "none",
        }
    if status in (1, 2, 13, 14, 126) and tokens:
        paths = [x for x in tokens if ("/" in x or x.startswith(".") or x.startswith("~"))]
        tgt = paths[0] if paths else tokens[-1]
        return {
            "cause": f"exit {status} from `{head}` — do the paths hold up?",
            "why": "classic first checks — does the target exist, is it readable. read-only, no mutations.",
            "fix": (f"test -e {tgt}; and echo exists; or echo missing; "
                    f"and test -r {tgt}; and echo readable; or echo unreadable"),
            "risk": "none",
        }
    return None
