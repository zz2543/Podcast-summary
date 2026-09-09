"""Anonymous Bilibili session state.

Bilibili rejects a share of anonymous requests with HTTP 412 regardless of the
headers sent; carrying a ``buvid`` browser fingerprint measurably lowers that
rate. The fingerprint comes from an open endpoint, so unlike an exported login
cookie it needs no account and never has to be refreshed by hand.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from pathlib import Path

import httpx

FINGERPRINT_URL = "https://api.bilibili.com/x/frontend/finger/spi"
REFERER = "https://www.bilibili.com/"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_FINGERPRINT_TTL_SECONDS = 6 * 3600
_COOKIE_LIFETIME_SECONDS = 365 * 24 * 3600

_lock = threading.Lock()
_cached: dict[str, str] | None = None
_cached_at = 0.0


def anonymous_cookies() -> dict[str, str] | None:
    """Return anonymous ``buvid`` cookies, or None when they cannot be fetched.

    Callers should carry on without cookies rather than fail: Bilibili still
    serves a share of requests that carry no fingerprint at all.
    """
    global _cached, _cached_at

    with _lock:
        now = time.monotonic()
        if _cached is not None and now - _cached_at < _FINGERPRINT_TTL_SECONDS:
            return dict(_cached)
        try:
            cookies = _fetch_fingerprint()
        except (httpx.HTTPError, KeyError, ValueError):
            return None
        _cached = cookies
        _cached_at = now
        return dict(cookies)


def write_cookiefile(path: Path, cookies: Mapping[str, str]) -> None:
    """Write ``cookies`` to ``path`` in the Netscape format yt-dlp reads."""
    expiry = int(time.time()) + _COOKIE_LIFETIME_SECONDS
    lines = ["# Netscape HTTP Cookie File"]
    lines.extend(
        f".bilibili.com\tTRUE\t/\tFALSE\t{expiry}\t{name}\t{value}"
        for name, value in cookies.items()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fetch_fingerprint() -> dict[str, str]:
    response = httpx.get(
        FINGERPRINT_URL,
        headers={"User-Agent": BROWSER_USER_AGENT, "Referer": REFERER},
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()["data"]
    return {"buvid3": data["b_3"], "buvid4": data["b_4"]}


def reset_cache() -> None:
    """Drop the cached fingerprint. Intended for tests."""
    global _cached, _cached_at
    with _lock:
        _cached = None
        _cached_at = 0.0
