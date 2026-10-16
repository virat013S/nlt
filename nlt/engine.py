"""Execution engine: run fish commands LIVE in a real pseudo-terminal.

Why pty: `sudo` must see a real terminal so IT can ask for the password —
nlt never captures, logs, or sees your password. Output is mirrored to the
screen and tailed for diagnosis.

Two defenses against a creative model:
  - bare interactive programs (fish, nvim, top...) are refused outright
  - headless runs watchdog: silence > N seconds → the child is terminated
"""
from __future__ import annotations

import os
import select
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

from .risk import is_interactive_bare
from .style import BAD, say

TAIL_KEEP = 2400


@dataclass
class ExecResult:
    status: int
    tail: str = ""
    used_pty: bool = False
    refused: bool = False


def fish_path() -> str | None:
    return shutil.which("fish") or os.environ.get("NLT_SHELL")


def run_live(cmd: str, *, cwd: str | None = None, tail_len: int = TAIL_KEEP,
             silence_timeout: float = 25.0) -> ExecResult:
    if os.name != "posix":
        return _run_plain(cmd, cwd)

    if is_interactive_bare(cmd):
        head = (cmd or "").strip().split()[0] if (cmd or "").strip() else "?"
        say(BAD(f"— refused: '{head}' opens its own interactive session — "
                "run that one in your own terminal —"))
        return ExecResult(status=-3, refused=True)

    shell = fish_path() or "/bin/sh"
    try:
        import pty
    except ImportError:  # pragma: no cover
        return _run_plain(cmd, cwd)

    pid, master = _run_in_pty(shell, cmd, cwd)
    acc = bytearray()
    stdin_fd = sys.stdin.fileno() if sys.stdin.isatty() else None
    status: int | None = None
    last_out = time.monotonic()

    try:
        while True:
            # relay typed input straight into the child's tty — this is the
            # only path your sudo password takes: your hand → sudo. direct.
            r, _, _ = select.select([master] + ([stdin_fd] if stdin_fd else []), [], [], 0.06)
            if stdin_fd and stdin_fd in r:
                try:
                    chunk = os.read(stdin_fd, 1024)
                    if not chunk:
                        os.write(master, b"\x04")
                        stdin_fd = None
                    else:
                        os.write(master, chunk)
                except OSError:
                    stdin_fd = None
            if master in r:
                try:
                    data = os.read(master, 4096)
                except OSError:  # EIO — child hung up
                    data = b""
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)  # mirror to screen
                acc.extend(data)
                del acc[:-tail_len * 2]
                last_out = time.monotonic()

            if stdin_fd is None and time.monotonic() - last_out > silence_timeout:
                say(BAD(f"— {silence_timeout:.0f}s of silence in headless mode — stopping —"))
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
                status = -2
                break

            wpid, st = os.waitpid(pid, os.WNOHANG)
            if wpid:
                status = os.waitstatus_to_exitcode(st)
                break
    except KeyboardInterrupt:
        say(BAD("— interrupted —"))
        try:
            os.kill(pid, signal.SIGINT)
            os.waitpid(pid, 0)
        except OSError:
            pass
        status = 130
    finally:
        if status is None:  # EOF before reap — always collect the exit code
            try:
                _, st = os.waitpid(pid, 0)
                status = os.waitstatus_to_exitcode(st)
            except (ChildProcessError, OSError):
                status = -1
        try:
            os.close(master)
        except OSError:
            pass

    tail = acc.decode("utf-8", errors="replace")[-tail_len:]
    return ExecResult(status=status, tail=tail, used_pty=True)


def _run_in_pty(shell: str, cmd: str, cwd: str | None):
    import pty
    pid, master = pty.fork()
    if pid == 0:  # child — its stdio IS the new terminal now
        try:
            if cwd:
                os.chdir(cwd)
            os.execvp(shell, [shell, "-c", cmd])
        except Exception as e:  # pragma: no cover
            os.write(2, f"exec failed: {e}".encode())
            os._exit(127)
    return pid, master


def _run_plain(cmd: str, cwd: str | None) -> ExecResult:
    """No pty available (Windows): pass-through run, no capture."""
    proc = subprocess.run(cmd, shell=True, cwd=cwd)
    return ExecResult(status=proc.returncode, tail="", used_pty=False)
