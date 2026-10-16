# ✦ nlt — the Natural Language Terminal

[![tests](https://github.com/virat013S/nlt/actions/workflows/tests.yml/badge.svg)](https://github.com/virat013S/nlt/actions/workflows/tests.yml)

A **local AI assistant that lives inside your fish shell**. Two things it does:

1. **Rescue** — a command failed? Press **`ctrl-g`** (or type `nlt`). nlt reads
   the failure, tells you what went wrong, and offers the fix. You sign off on
   it; it runs *in your session* — fish history, your aliases, real `sudo`
   prompts, everything.
2. **Tasks** — `nlt "make a backup of my ssh config"` — plain English goes in,
   fish commands come out, you confirm, they run. Failed? nlt asks you what
   happened (or reads the output itself) and tries again.

Everything runs **locally on Ollama**. No cloud, no keys, no telemetry.
Nothing is executed without your sign-off, and **your password is handled by
sudo alone** — nlt never sees it.

```
✦ make /tmp/party and write "amen" into guest.txt there
   1. mkdir -p /tmp/party [mutates things]

✦ incorrect path
   the one of the paths doesn't exist

→  mkdir /tmp/party [mutates things]
(run this fix [r/N]?)
```

## Installing

You need Python 3.9+ (and fish 4.x for the integration; the bare tool works everywhere).

```bash
git clone https://github.com/virat013S/nlt
cd nlt
python3 -m pip install --user .          # or pipx install .
```

Give it a brain (local, free):

```bash
ollama pull gemma3:1b   # tiny & fine
ollama pull gemma3:4b   # noticeably smarter for multi-step tasks
```

Wire it into fish:

```bash
nlt fish install        # ctrl-g rescue + failure capture + completions
exec fish               # reload
```

Health check:

```bash
nlt doctor
```

## The daily loop

```bash
# somewhere in your fish shell...
ls /etc/pasword                     # oops, typo
<ctrl-g>                            # nlt wakes up
#  ✦ "incorrect path — 'pasword' does not exist"
#  → suggest: sudo ls /etc/password
#  [r/N] → r → runs in-session, sudo asks password the normal way

nlt "count lines of code in this repo by extension"      # one-shot task
nlt chat                            # sit down and chain tasks until 'exit'
nlt rescue-last --dry-run           # inspect the fix before ever running it
nlt history                         # everything you and nlt have done
```

Keybinding: `ctrl-g` (runs `nlt rescue-last --print-only` and `eval`s the
confirmed fix in your session), `alt-h` as an alternative.

## Personas

| flag     | voice                                                |
|----------|------------------------------------------------------|
| `guide`  | friendly default. *(nlt --persona guide)*            |
| `brisk`  | four words maximum.                                  |
| `bard`   | narrates every failure in epic verse. 📜             |

## Safety model

- AI-proposed commands are **always** shown before execution; sign-off required.
- Classified risks are badge-stamped: `read-only`, `mutates things`,
  `needs sudo`, `⚠ DANGEROUS`. Danger-class commands require typing `yes`.
- Bare interactive programs (a hallucinated `fish`, `nvim`, `top`…) are
  **refused outright** — they'd wait on a tty forever.
- Headless runs have a silence watchdog: no output for 25s → child terminated.
- `sudo` password: reaches sudo through a real pty, matched with a normal sudo
  prompt. nlt never reads it, stores it, or sends it anywhere.

## Platform

| platform | status                                                    |
|----------|-----------------------------------------------------------|
| Linux    | ✅ full (fish integration + pty engine)                   |
| macOS    | ✅ full (same)                                            |
| Windows  | ✅ standalone tasks (no pty: no capture, no fish binding)  |
| CI       | ✅ tested on ubuntu + macos + windows on every push        |

Model is picked automatically (`llama3` > `qwen` > `gemma` …), or force one:
`nlt --model gemma3:4b "..."`. Set `OLLAMA_HOST` if the server isn't local.

## Files

| path                              | what lives there                                  |
|-----------------------------------|---------------------------------------------------|
| `~/.local/state/nlt/`             | failure capture (`last-<pid>.state`), `history.jsonl` |
| `~/.config/fish/conf.d/nlt.fish`  | the capture hook + ctrl-g bind                    |
| `~/.config/fish/completions/nlt.fish` | tab completions for the `nlt` command         |

`nlt fish uninstall` removes it all.

## Tests

```bash
python3 -m pytest tests -q
```

## License

MIT
