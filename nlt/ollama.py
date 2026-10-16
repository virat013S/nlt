"""The connection to the local model server (Ollama). Local, private, free."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
PREFER = ("llama3", "qwen", "gemma", "mistral", "phi", "tinyllama")
VISION_HINTS = ("moondream", "vision", "clip")


def ping(timeout: float = 1.5) -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{BASE}/api/tags", timeout=timeout) as r:
            models = json.load(r).get("models", [])
        override = os.environ.get("NLT_MODEL")
        names = ([override] if override else []) + [m["name"] for m in models]
        return names or None
    except Exception:
        return None


def pick_model(models: list[str]) -> str | None:
    texty = [m for m in models if not any(h in m.lower() for h in VISION_HINTS)] or models
    for want in PREFER:
        for m in texty:
            if want in m.lower():
                return m
    return texty[0] if texty else None


def chat_json(model: str, system: str, user: str, *, timeout: float = 180.0) -> dict | None:
    body = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.15, "num_ctx": 4096},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    keep = os.environ.get("NLT_KEEP_ALIVE")
    if keep:
        # e.g. NLT_KEEP_ALIVE=5s → the model unloads right after answering,
        # leaving RAM exactly as you left it
        body["keep_alive"] = keep
    req = urllib.request.Request(f"{BASE}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = json.load(r)["message"]["content"]
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            KeyError, json.JSONDecodeError):
        return None
    return _parse(content)


def _parse(content: str) -> dict | None:
    s, e = content.find("{"), content.rfind("}")
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(content[s:e + 1])
    except json.JSONDecodeError:
        return None
