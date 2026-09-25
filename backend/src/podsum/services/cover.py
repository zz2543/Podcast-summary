"""Keep a video's cover image next to its audio.

The episode list is a wall of titles otherwise; the cover is what a reader
recognises a video by. It is saved as ``cover.jpg`` in the episode directory,
re-encoded by ffmpeg so every source format (YouTube hands out WebP) arrives
as one small JPEG the clients can draw without caring where it came from.

Everything here is best-effort: a missing cover must never fail the job that
fetched the audio, so failures are logged and swallowed.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Mapping
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

COVER_FILENAME = "cover.jpg"
#: Cards are at most a few hundred points wide; 720 px covers Retina at 2x.
COVER_MAX_WIDTH = 720
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
#: YouTube lists dozens of sizes; the first few good ones are all that matter.
_MAX_CANDIDATES = 4


def cover_path(episode_dir: Path) -> Path:
    return episode_dir / COVER_FILENAME


def episode_cover_path(data_dir: str, episode_id: str, data_root: Path | None) -> Path:
    """Where an episode's cover is, wherever the server happens to run from.

    Early episodes stored ``data_dir`` as ``data/<id>``, relative to whatever
    the working directory was then. The packaged app runs the server from
    inside its bundle, where that path points nowhere; the episode directory
    is still ``DATA_DIR/<id>``, so fall back to that.
    """
    episode_dir = Path(data_dir)
    if not episode_dir.is_absolute() and not episode_dir.is_dir() and data_root is not None:
        episode_dir = data_root / episode_id
    return cover_path(episode_dir)


def thumbnail_urls(info: Mapping[str, object]) -> list[str]:
    """Cover candidates yt-dlp found for a video, best first.

    Only a processed result carries ``thumbnail``; the lookup for old episodes
    skips processing and gets the raw ``thumbnails`` list instead. Its best
    entry is not guaranteed to exist — YouTube's maxresdefault is missing for
    many older uploads — so the caller tries them in turn.
    """
    urls: list[str] = []
    chosen = info.get("thumbnail")
    if isinstance(chosen, str) and chosen:
        urls.append(chosen)
    listed = info.get("thumbnails")
    if isinstance(listed, list):
        entries = [
            (index, entry)
            for index, entry in enumerate(listed)
            if isinstance(entry, Mapping) and isinstance(entry.get("url"), str)
        ]
        # Ordered worst to best; ``preference`` overrides the order where set.
        entries.sort(key=lambda pair: (pair[1].get("preference") or 0, pair[0]), reverse=True)
        urls.extend(str(entry["url"]) for _, entry in entries)
    seen: set[str] = set()
    result: list[str] = []
    for url in map(_https, urls):
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _https(url: str) -> str:
    # Bilibili reports its thumbnails as plain http://; the same URL works over
    # https, and plain http may be refused outright.
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def save_first_cover(
    image_urls: list[str], episode_dir: Path, *, referer: str | None = None
) -> Path | None:
    """Save the first candidate that downloads and decodes; None when none does."""
    for image_url in image_urls[:_MAX_CANDIDATES]:
        saved = save_cover(image_url, episode_dir, referer=referer)
        if saved is not None:
            return saved
    return None


def save_cover(image_url: str, episode_dir: Path, *, referer: str | None = None) -> Path | None:
    """Download ``image_url`` into ``episode_dir/cover.jpg``; None on any failure."""
    target = cover_path(episode_dir)
    raw = episode_dir / "cover.download"
    headers = {"Referer": referer} if referer else {}
    try:
        with httpx.Client(follow_redirects=True, timeout=20.0, headers=headers) as client:
            response = client.get(image_url)
            response.raise_for_status()
            if len(response.content) > _MAX_IMAGE_BYTES:
                raise ValueError("cover image too large")
            raw.write_bytes(response.content)
        _encode_jpeg(raw, target)
        return target
    except Exception as exc:  # noqa: BLE001 - a cover is never worth failing a job over
        logger.warning("could not save cover from %s: %s", image_url, exc)
        target.unlink(missing_ok=True)
        return None
    finally:
        raw.unlink(missing_ok=True)


def _encode_jpeg(source: Path, target: Path) -> None:
    tmp = target.with_suffix(".tmp.jpg")
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale='min({COVER_MAX_WIDTH},iw)':-2",
            "-q:v",
            "4",
            str(tmp),
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip() or "ffmpeg failed")
    tmp.replace(target)
