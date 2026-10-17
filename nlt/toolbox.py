"""The toolbox — nlt's CLI-tool help desk, zero-model tier of it.

Three jobs:
  1. spelling rescue: "install firefoks" becomes "install firefox" (footgun
     guarded — the note rides the plan, abort if wrong), before an install
     plan is built.
  2. cheat sheets: "help with nmap" / "what does git do" prints a curated
     card: the one quick command + three more + the docs pointer.
  3. name suggestions: unrecognized words that sit next to real tool names
     get a "did you mean ...?" note, and exit-127s get the same rescue.

Names come from PATH first (what can actually run here), then the pacman
repo db, then an embedded list of the everyday tools. No network, no model.
"""
from __future__ import annotations

import difflib
import os
import re
import subprocess
import time

# The everyday half of terminal life — enough for the typos people type.
COMMON = (
    "bash", "zsh", "fish", "vim", "neovim", "nvim", "nano", "micro", "emacs",
    "git", "curl", "wget", "ssh", "scp", "rsync", "tar", "unzip", "gzip",
    "zstd", "zip", "systemctl", "journalctl", "docker", "podman", "pacman",
    "apt", "apt-get", "dnf", "brew", "pip", "pip3", "pipx", "npm", "cargo",
    "uv", "python", "python3", "node", "deno", "gcc", "clang", "make",
    "cmake", "gdb", "strace", "ltrace", "htop", "btop", "top", "kill",
    "pkill", "ln", "chmod", "chown", "crontab", "tree", "man", "less",
    "grep", "rg", "ripgrep", "sed", "awk", "jq", "yq", "find", "fd",
    "du", "df", "free", "ps", "ss", "netstat", "ip", "ping", "traceroute",
    "dig", "nslookup", "whois", "uname", "uptime", "hostname", "which",
    "firefox", "chromium", "chrome", "nmap", "wireshark", "tcpdump",
    "aria2", "ffmpeg", "convert", "magick", "feh", "mpv", "cmus", "obs",
    "gimp", "inkscape", "code", "sublime", "kate", "geany", "kitty",
    "alacritty", "tmux", "screen", "lolcat", "cowsay",
    "sl", "fastfetch", "neofetch", "hyfetch", "iotop", "openssh",
    "openssl", "clangd", "shellcheck", "shfmt", "hyprland",
    "niri", "yay", "paru", "flatpak", "snap", "steam", "lutris", "heroic",
    "qbittorrent", "transmission", "vlc", "audacity", "blender", "cmatrix",
)

_POOL: tuple[frozenset, float] = (frozenset(), 0.0)
_POOL_TTL = 120.0


def pool() -> frozenset:
    """Names that actually exist here: PATH first, then the pacman db."""
    global _POOL
    now = time.monotonic()
    if now - _POOL[1] < _POOL_TTL and _POOL[0]:
        return _POOL[0]
    names: set[str] = set(COMMON)
    try:
        for d in os.environ.get("PATH", "").split(os.pathsep):
            if not d or not os.path.isdir(d):
                continue
            try:
                with os.scandir(d) as it:
                    for entry in it:
                        if entry.is_file() and os.access(
                                entry.path, os.X_OK):
                            names.add(entry.name.lower())
            except OSError:
                continue
    except Exception:
        pass
    if os.path.exists("/etc/pacman.conf"):
        try:
            out = subprocess.run(["pacman", "-Slq"], capture_output=True,
                                 text=True, timeout=8).stdout
            names.update(w.strip().lower() for w in out.split() if w.strip())
        except Exception:
            pass
    _POOL = (frozenset(names), now)
    return _POOL[0]


def suggest(word: str, count: int = 2) -> list[str]:
    """Closest real names for a misspelling — '' when nothing is close."""
    word = (word or "").strip().lower()
    if len(word) < 2:
        return []
    return difflib.get_close_matches(word, pool(), n=count, cutoff=0.6)


def fix(name: str) -> tuple[str, str]:
    """(name-or-correction, note-or-'') for instance names in plans."""
    name = (name or "").strip()
    if not name or name.lower() in pool():
        return name, ""
    hit = suggest(name, 1)
    if hit:
        return (hit[0],
                f"assumed `{name}` → `{hit[0]}` (closest real name) — "
                "abort if wrong")
    return name, ""


# ------------------------------------------------------------------ cheats
CHEATS: dict[str, dict] = {
    "nmap": {"what": "the network scanner — hosts, ports, service guesses",
             "quick": "sudo nmap -sn 192.168.1.0/24   # who is alive on your LAN",
             "more": ["nmap -sn 192.168.1.0/24        # quick ping sweep, no root",
                      "nmap localhost                   # your own open ports",
                      "sudo nmap -sV <host>            # probe service versions",
                      "sudo nmap -A <host>             # everything, loud"],
             "docs": "man nmap · nmap.org/book/man.html"},
    "git": {"what": "version control — commit, branch, merge, publish",
            "quick": "git status -sb   # where you are, small",
            "more": ["git add -A; and git commit -m \"msg\"",
                     "git switch -c new-branch         # branch + move to it",
                     "git log --oneline -10           # recent history, tiny",
                     "git push origin main            # publish"],
            "docs": "man git"},
    "curl": {"what": "talk to URLs — GET, POST, headers, downloads",
             "quick": "curl -s https://api.github.com/zen",
             "more": ["curl -fLO <url>          # download, fail on error",
                      "curl -I <url>            # headers only",
                      'curl -X POST -d \'{"a":1}\' -H "Content-Type: json" <url>',
                      'curl -s "wttr.in/kyoto?format=3"   # quick weather'],
             "docs": "man curl · everythingcurl.com"},
    "wget": {"what": "the fetcher — mirrors, resumes, whole trees",
             "quick": "wget <url>",
             "more": ["wget -c <url>            # resume a broken download",
                      "wget -q <url>            # quiet",
                      "wget -r -np <url>        # mirror a subtree"],
             "docs": "man wget"},
    "ssh": {"what": "shell on another machine",
            "quick": "ssh user@host",
            "more": ["ssh -p 2222 user@host     # a different port",
                     "ssh -L 8080:localhost:80 host   # tunnel a local port",
                     "scp file.txt user@host:~/     # send one file"],
            "docs": "man ssh"},
    "scp": {"what": "copy files over ssh",
            "quick": "scp file.txt user@host:~/",
            "more": ["scp user@host:~/log .     # pull one back",
                     "scp -r folder user@host:~/ # whole folder"],
            "docs": "man scp"},
    "rsync": {"what": "sync folders — deltas, excludes, dry runs",
              "quick": "rsync -av src/ dest/",
              "more": ["rsync -avn src/ dest/     # DRY RUN, shows only",
                       "rsync -av --delete src/ dest/   # mirror exactly",
                       "rsync -av src/ user@host:dest/ # over ssh"],
              "docs": "man rsync"},
    "tar": {"what": "archive maker — .tar.gz friends only",
            "quick": "tar -czf out.tar.gz folder/",
            "more": ["tar -xzf out.tar.gz       # pull it apart",
                     "tar -tf out.tar.gz        # list without unpacking",
                     "tar -czf ~/backups/x.tar.gz .   # archive now"],
            "docs": "man tar"},
    "unzip": {"what": ".zip unpacker",
              "quick": "unzip file.zip -d out/",
              "more": ["unzip -l file.zip        # list first",
                       "unzip -o file.zip        # overwrite"],
              "docs": "man unzip"},
    "systemctl": {"what": "services — status, start/stop, enable",
                  "quick": "systemctl status <service>",
                  "more": ["sudo systemctl start <service>",
                           "sudo systemctl restart <service>",
                           "systemctl --failed          # what is broken",
                           "systemctl list-unit-files --state=enabled"],
                  "docs": "man systemctl"},
    "journalctl": {"what": "the systemd log reader",
                   "quick": "journalctl -n 40 --no-pager",
                   "more": ["journalctl -u ssh -n 50   # one unit",
                            "journalctl -b             # this boot only",
                            "journalctl -f             # follow, live"],
                   "docs": "man journalctl"},
    "docker": {"what": "containers — run, build, clean",
               "quick": "docker ps",
               "more": ["docker run -it --rm image",
                        "docker build -t name .",
                        "docker system prune       # reclaim junk"],
               "docs": "man docker"},
    "pacman": {"what": "package manager, arch-family",
               "quick": "pacman -S --needed <pkg>",
               "more": ["pacman -Ss <word>       # search the repos",
                        "pacman -Qs <word>       # search what's installed",
                        "sudo pacman -Syu        # update everything",
                        "pacman -Ql <pkg>        # what it owns"],
               "docs": "man pacman"},
    "apt": {"what": "package manager, debian-family",
            "quick": "sudo apt install <pkg>",
            "more": ["apt search <word>",
                     "sudo apt update; and sudo apt upgrade",
                     "apt show <pkg>"],
            "docs": "man apt"},
    "pip": {"what": "python packages — your env, your rules",
            "quick": "pip install <pkg>",
            "more": ["pip show <pkg>",
                     "pip install --upgrade <pkg>",
                     "pipx install <cli-tool>    # better for CLIs"],
            "docs": "man pip"},
    "python": {"what": "run python — scripts, REPL, one-liners",
               "quick": "python3 script.py",
               "more": ["python3 -m venv .venv       # a sandbox",
                        "python3 -m pip install -U pip",
                        'python3 -c "import sys; print(sys.version)"'],
               "docs": "man python3"},
    "ffmpeg": {"what": "the media swiss army knife",
               "quick": 'ffmpeg -i in.mp4 out.webm',
               "more": ["ffmpeg -i in.mp4 -vn out.m4a       # audio out",
                         "ffmpeg -ss 0 -t 10 -i in.mp4 clip.mp4  # first 10s",
                         "ffmpeg -i in.gif -vf scale=480:-1 out.gif"],
               "docs": "man ffmpeg · ffmpeg.org"},
    "grep": {"what": "search inside files",
             "quick": 'grep -rn "TODO" .',
             "more": ['grep -n "err" file.log      # line numbers',
                      "grep -ri key folder/       # case-insensitive, tree",
                      "grep -c word files...      # just the count"],
             "docs": "man grep"},
    "sed": {"what": "stream editor — swap, delete, in place",
            "quick": 'sed -i \'s/old/new/g\' file',
            "more": ["sed -n '10,20p' file      # print a range",
                     "sed -i.bak 's/a/b/' file  # keep a backup",
                     "sed '/^#/d' file          # drop comments"],
            "docs": "man sed"},
    "awk": {"what": "column cruncher",
            "quick": "awk '{print $1}' file",
            "more": ["ps aux | awk '{print $2, $11}'",
                     "df -h | awk 'NR>1 {print $5, $6}'",
                     "awk -F, '{print NF}' file.csv   # field count per row"],
            "docs": "man awk"},
    "find": {"what": "hunt files by name/type/size",
             "quick": "find . -maxdepth 3 -name '*.jpg'",
             "more": ["find . -type f -size +100M    # big files",
                      "find . -mtime -1             # changed today",
                      "find . -type d -name node_modules -exec rm -rf {} +"],
             "docs": "man find"},
    "du": {"what": "what is eating the disk",
           "quick": "du -sh ./* | sort -rh | head",
           "more": ["du -sh .               # this folder's total",
                    "du --max-depth=1 -h .   # one level down"],
           "docs": "man du"},
    "df": {"what": "free space per filesystem",
           "quick": "df -h",
           "more": ["df -h ~                 # just home",
                    "df -i                   # inodes, not bytes"],
           "docs": "man df"},
    "free": {"what": "RAM, human units",
             "quick": "free -h",
             "more": ["free -h -s 2             # refresh every 2s",
                      "free -m                  # mebibytes"],
             "docs": "man free"},
    "ps": {"what": "process list",
           "quick": "ps -eo pid,pcpu,pmem,comm --sort=-pcpu | head -12",
           "more": ["ps aux | grep fish        # one process",
                    "pgrep -f spotify           # just the pid",
                    "pkill -f spotify           # stop it (own risk)"],
           "docs": "man ps"},
    "htop": {"what": "interactive process viewer",
             "quick": "htop",
             "more": ["htop -u $USER         # only yours",
                      "F9 → kill, F10 → quit  # inside the UI"],
             "docs": "man htop"},
    "chmod": {"what": "permissions — make it executable, lock it down",
              "quick": "chmod +x script.sh",
              "more": ["chmod 600 key.pem        # private: only you",
                       "chmod 644 file            # normal file",
                       "chmod -R +x bin/          # recursive"],
              "docs": "man chmod"},
    "ln": {"what": "links — symlinks especially",
           "quick": "ln -s ~/configs/vitro ~/.config/vitro",
           "more": ["ln -s target name       # symlink",
                    "ln file hard              # hard link"],
           "docs": "man ln"},
    "crontab": {"what": "scheduled jobs",
                "quick": "crontab -e",
                "more": ["crontab -l              # what is scheduled",
                         "0 9 * * 1 job           # mondays 9:00"],
                "docs": "man crontab · crontab.guru"},
    "tree": {"what": "a folder at a glance",
             "quick": "tree -L 2",
             "more": ["tree -a                  # hidden things too",
                      "tree -d                  # just folders"],
             "docs": "man tree"},
    "ss": {"what": "sockets — who listens, who talks",
           "quick": "ss -tlnp",
           "more": ["ss -tln | head          # servers only",
                    "ss -s                    # summary"],
           "docs": "man ss"},
    "ip": {"what": "addresses, routes, links (iproute2)",
           "quick": "ip a",
           "more": ["ip r                     # routes",
                    "ip -4 a show wlan0       # one interface",
                    "ip neigh                 # arp table"],
           "docs": "man ip"},
    "ping": {"what": "reach check, round trip",
             "quick": "ping -c 3 1.1.1.1",
             "more": ["ping -c 3 example.com",
                      "ping -i 0.2 -c 5 host    # faster, careful"],
             "docs": "man ping"},
    "man": {"what": "the manual, like it says on the tin",
            "quick": "man nmap",
            "more": ["man -k network          # search by keyword",
                   "man printf               # even shells here"],
            "docs": "man man"},
}


HELP_RX = (r"\b(help|usage|how\s+(?:do\s+)?i|how\s+to|how\s+does|what\s+(?:does|is)"
           r"|cheats?(?:sheets?)?|examples?|flags?|options?)\b")
_TOOL_RX = r"([a-zA-Z][\w.\-]*)"


def _tool_token(task: str) -> str:
    known = set(CHEATS)
    for tok in re.findall(_TOOL_RX, task.lower()):
        if tok.rstrip("s") in known:
            known_word = tok.rstrip("s")
            return known_word if known_word in known else tok
        if tok in known:
            return tok
    return ""


def help_for(task: str) -> dict | None:
    """A cheat-sheet request about a tool we know → the card to print."""
    if not re.search(HELP_RX, task, re.IGNORECASE):
        return None
    tool = _tool_token(task)
    if not tool:
        return None
    card = CHEATS[tool]
    return {"tool": tool, "what": card["what"], "quick": card["quick"],
            "more": card["more"], "docs": card.get("docs", f"man {tool}")}


NOISE = frozenset((
    "the", "and", "for", "from", "with", "into", "my", "our", "this", "that",
    "show", "make", "use", "using", "help", "please", "can", "could", "you",
    "we", "them", "it", "file", "files", "folder", "what", "how", "does",
    "install", "download", "copy", "move", "delete", "list", "view", "open",
    "scan", "running", "find", "about", "everything", "thing", "network",
    "ports", "internet", "system", "machine", "computer", "there", "here",
))


def suggest_note(task: str) -> str:
    """For unknown sentences — 'did you mean ...?' when a near name exists.

    Every meaningful word gets a candidate; the best-ranked one wins, so
    'nmaap scan the network' suggests nmap (0.89) not screen (0.66)."""
    best = ("", 0.0)
    for tok in re.findall(r"[a-zA-Z][\w.\-]{2,}", task):
        if tok.lower() in NOISE:
            continue
        hits = difflib.get_close_matches(tok.lower(), pool(), n=1, cutoff=0.5)
        if hits:
            ratio = difflib.SequenceMatcher(None, tok.lower(), hits[0]).ratio()
            if ratio >= 0.75 and best[1] < ratio < 1.0:
                best = (hits[0], ratio)
    if not best[0]:
        return ""
    return (f" — did you mean `{best[0]}`? "
            f"`help with {best[0]}` prints its cheat sheet")


def local_net() -> str:
    """Best-effort local subnet for network-wide scans; localhost otherwise."""
    try:
        out = subprocess.run(["ip", "-4", "route"], capture_output=True,
                             text=True, timeout=3).stdout
        for line in out.splitlines():
            if line.startswith("10.") or line.startswith("192.168") \
                    or line.startswith("172."):
                net = line.split()[0]
                if "/" in net and not net.endswith("/32"):
                    return net
    except Exception:
        pass
    return "localhost"
