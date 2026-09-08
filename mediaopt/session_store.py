"""Temporary server-side storage for a draft in progress.

Deliberately in-memory and short-lived: the app asks for no account and stores nothing
permanently. A draft lives for TTL seconds after its last touch and is then dropped.
Restarting the server clears everything, which is stated in the UI rather than hidden -
a user who has spent ten minutes entering a medium needs to know it is not saved.

Single-process by design (Render's free tier runs one worker). If you scale to several
workers, swap this for Redis; the interface is get/put/clear and nothing else.
"""
from __future__ import annotations
import time, uuid, threading

TTL_SECONDS = 8 * 3600
_LOCK = threading.Lock()
_STORE: dict[str, tuple[float, dict]] = {}


def _sweep() -> None:
    now = time.time()
    for k in [k for k, (t, _) in _STORE.items() if now - t > TTL_SECONDS]:
        _STORE.pop(k, None)


def new_id() -> str:
    return uuid.uuid4().hex


def get(sid: str | None) -> dict:
    if not sid:
        return {}
    with _LOCK:
        _sweep()
        rec = _STORE.get(sid)
        if not rec:
            return {}
        _STORE[sid] = (time.time(), rec[1])
        return rec[1]


def put(sid: str, draft: dict) -> None:
    with _LOCK:
        _sweep()
        _STORE[sid] = (time.time(), draft)


def clear(sid: str | None) -> None:
    if sid:
        with _LOCK:
            _STORE.pop(sid, None)
