from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import yt_dlp

from podsum.config import Settings
from podsum.persistence.models import new_ulid
from podsum.services import _bilibili_session

MAX_FILE_BYTES = 1_000_000_000
MAX_DURATION_SECONDS = 21_600
CHUNK_SIZE = 1024 * 1024

BILIBILI_HOSTS = ("bilibili.com", "b23.tv")

# Share buttons hand out a whole sentence, e.g.
# 【标题】https://www.bilibili.com/video/BV14dYx6iEwC?vd_source=e352aac...
# so what a user pastes is rarely a bare URL. CJK punctuation and fullwidth
# forms are excluded from the match because they abut URLs without whitespace.
_URL_PATTERN = re.compile(r"https?://[^\s<>\"'\u3000-\u303f\uff00-\uffef]+")
_TRAILING_PUNCTUATION = ".,;:!?)]}\"'"

# These identify the sharer rather than the media. Dropping them also lets two
# shares of the same video deduplicate against each other.
_TRACKING_PARAMS = frozenset(
    {
        "vd_source",
        "spm_id_from",
        "from_source",
        "from_spmid",
        "share_source",
        "share_medium",
        "share_plat",
        "share_tag",
        "share_session_id",
        "unique_k",
        "msource",
        "bbid",
        "up_id",
        "plat_id",
        "buvid",
        "si",
        "feature",
        "pp",
    }
)

# Word boundaries matter here: a plain "age" substring also matches the very
# common "Unable to download webpage", which would report a throttled request
# as an authentication problem.
_RESTRICTED_PATTERN = re.compile(
    r"\b(?:age[ -]?restricted|age[ -]?gate\w*|region|geo[ -]?block\w*|drm"
    r"|private video|requires? login|sign in|members?[ -]?only)\b",
    re.IGNORECASE,
)
_THROTTLED_PATTERN = re.compile(
    r"\b(?:412|429|precondition failed|too many requests|rate[ -]?limit\w*"
    r"|temporarily unavailable)\b",
    re.IGNORECASE,
)
# Transport failures mid-download are just as recoverable as a throttled
# request, and just as common over a long audio fetch.
_TRANSIENT_PATTERN = re.compile(
    r"(?:\bssl\b|eof occurred|incomplete read|remote end closed"
    r"|connection (?:reset|aborted|refused|error)|timed out|read timeout"
    r"|temporary failure in name resolution)",
    re.IGNORECASE,
)


class IngestError(ValueError):
    pass


class PayloadTooLarge(IngestError):
    pass


class UnsupportedMedia(IngestError):
    pass


class UploadLike(Protocol):
    filename: str | None

    async def read(self, size: int = -1) -> bytes:
        raise NotImplementedError


@dataclass(frozen=True)
class IngestedAudio:
    episode_id: str
    original_path: Path
    normalized_path: Path
    duration_seconds: int
    file_size_bytes: int
    detected_ext: str
    title: str | None = None
    podcast_name: str | None = None
    source_ref: str | None = None


async def ingest_local_file(
    upload: UploadLike,
    settings: Settings,
    episode_id: str | None = None,
) -> IngestedAudio:
    episode_id = episode_id or new_ulid()
    episode_dir = settings.DATA_DIR / episode_id
    episode_dir.mkdir(parents=True, exist_ok=False)
    original_tmp = episode_dir / "audio.original.upload"

    try:
        file_size = await _write_upload(upload, original_tmp)
        detected_ext = _detect_audio_ext(original_tmp)
        original_path = episode_dir / f"audio.original.{detected_ext}"
        original_tmp.rename(original_path)

        duration_seconds = await _probe_duration_seconds(original_path)
        if duration_seconds > MAX_DURATION_SECONDS:
            raise PayloadTooLarge("audio duration exceeds 6 hour limit")

        normalized_path = episode_dir / "audio.normalized.mp3"
        await _run_ffmpeg_normalize(original_path, normalized_path)
        return IngestedAudio(
            episode_id=episode_id,
            original_path=original_path,
            normalized_path=normalized_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size,
            detected_ext=detected_ext,
        )
    except Exception:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise


async def ingest_direct_url(
    url: str,
    settings: Settings,
    episode_id: str | None = None,
) -> IngestedAudio:
    # A typo'd or scheme-less link would otherwise surface as an httpx
    # UnsupportedProtocol deep inside the download, which the API layer does not
    # catch: the caller got a 500 for what is plainly a bad input. Checking here
    # also keeps a rejected link from leaving an empty episode directory behind.
    scheme = urlsplit(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise IngestError("source_ref must be an http:// or https:// URL")

    episode_id = episode_id or new_ulid()
    episode_dir = settings.DATA_DIR / episode_id
    episode_dir.mkdir(parents=True, exist_ok=False)
    original_tmp = episode_dir / "audio.original.download"

    try:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                head = await client.head(url)
                head.raise_for_status()
                _validate_audio_content_type(head.headers.get("content-type"))
                content_length = head.headers.get("content-length")
                if content_length is not None and int(content_length) > MAX_FILE_BYTES:
                    raise PayloadTooLarge("audio file exceeds 1 GB limit")

                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    _validate_audio_content_type(response.headers.get("content-type"))
                    file_size = await _write_response_stream(response, original_tmp)
        except IngestError:
            # PayloadTooLarge / UnsupportedMedia already say the right thing.
            raise
        except httpx.HTTPStatusError as exc:
            # A 403 from a video site's HTML page used to escape as a bare httpx
            # error, so a mis-classified link came back to the caller as a 500.
            raise IngestError(
                f"source URL returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise IngestError(f"could not fetch source URL: {exc}") from exc

        detected_ext = _detect_audio_ext(original_tmp)
        original_path = episode_dir / f"audio.original.{detected_ext}"
        original_tmp.rename(original_path)

        duration_seconds = await _probe_duration_seconds(original_path)
        if duration_seconds > MAX_DURATION_SECONDS:
            raise PayloadTooLarge("audio duration exceeds 6 hour limit")

        normalized_path = episode_dir / "audio.normalized.mp3"
        await _run_ffmpeg_normalize(original_path, normalized_path)
        return IngestedAudio(
            episode_id=episode_id,
            original_path=original_path,
            normalized_path=normalized_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size,
            detected_ext=detected_ext,
        )
    except Exception:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise


def extract_url(text: str) -> str:
    """Return the first URL in ``text``, or the trimmed text when it holds none."""
    match = _URL_PATTERN.search(text)
    if match is None:
        return text.strip()
    return match.group(0).rstrip(_TRAILING_PUNCTUATION)


def normalize_video_url(text: str) -> str:
    """Pull the URL out of pasted share text and drop tracking parameters."""
    url = extract_url(text)
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if name not in _TRACKING_PARAMS
    ]
    return urlunsplit(parts._replace(query=urlencode(kept)))


async def ingest_video(
    url: str,
    settings: Settings,
    episode_id: str | None = None,
) -> IngestedAudio:
    episode_id = episode_id or new_ulid()
    episode_dir = settings.DATA_DIR / episode_id
    episode_dir.mkdir(parents=True, exist_ok=False)

    try:
        info, original_path = await asyncio.to_thread(
            _download_video_audio, url, episode_dir, settings
        )
        duration = info.get("duration")
        duration_seconds = int(round(float(duration))) if duration is not None else await _probe_duration_seconds(original_path)
        if duration_seconds > MAX_DURATION_SECONDS:
            raise PayloadTooLarge("audio duration exceeds 6 hour limit")

        file_size = original_path.stat().st_size
        if file_size > MAX_FILE_BYTES:
            raise PayloadTooLarge("audio file exceeds 1 GB limit")

        normalized_path = episode_dir / "audio.normalized.mp3"
        await _run_ffmpeg_normalize(original_path, normalized_path)
        return IngestedAudio(
            episode_id=episode_id,
            original_path=original_path,
            normalized_path=normalized_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size,
            detected_ext=original_path.suffix.lstrip(".") or "mp3",
            title=info.get("title"),
            podcast_name=info.get("channel") or info.get("uploader"),
            source_ref=info.get("webpage_url") or url,
        )
    except yt_dlp.utils.DownloadError as exc:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise UnsupportedMedia(_video_error_message(exc)) from exc
    except Exception:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise


def _download_video_audio(
    url: str,
    episode_dir: Path,
    settings: Settings,
) -> tuple[dict[str, object], Path]:
    """Download audio with yt-dlp, retrying hosts that throttle anonymous traffic.

    Bilibili rejects a share of anonymous requests with HTTP 412 while the
    extractor is still fetching the page, which yt-dlp's own `extractor_retries`
    does not cover. Each retry therefore happens here, with a fresh YoutubeDL.
    """
    cookiefile, cookiefile_is_temporary = _prepare_cookiefile(url, episode_dir, settings)
    attempts = settings.YTDLP_MAX_ATTEMPTS
    try:
        for attempt in range(1, attempts + 1):
            try:
                return _extract_audio(url, episode_dir, cookiefile)
            except yt_dlp.utils.DownloadError as exc:
                if attempt == attempts or not _is_retryable(exc):
                    raise
                _clear_partial_downloads(episode_dir)
                time.sleep(settings.YTDLP_RETRY_DELAY_SECONDS * attempt)
        raise UnsupportedMedia("Video download exhausted all attempts")
    finally:
        if cookiefile is not None and cookiefile_is_temporary:
            cookiefile.unlink(missing_ok=True)


def _extract_audio(
    url: str,
    episode_dir: Path,
    cookiefile: Path | None,
) -> tuple[dict[str, object], Path]:
    options: dict[str, object] = {
        "format": "bestaudio/best",
        "outtmpl": str(episode_dir / "audio.original.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # yt-dlp normalises this to a set; handing it a bare string makes it
        # iterate the characters and silently drop the component.
        "remote_components": {"ejs:github"},
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    if cookiefile is not None:
        options["cookiefile"] = str(cookiefile)
    if _is_bilibili(url):
        options["http_headers"] = {"Referer": _bilibili_session.REFERER}

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    mp3_path = episode_dir / "audio.original.mp3"
    if mp3_path.exists():
        return info, mp3_path

    candidates = sorted(episode_dir.glob("audio.original.*"))
    if not candidates:
        raise UnsupportedMedia("Video audio extraction produced no file")
    return info, candidates[0]


def _prepare_cookiefile(
    url: str,
    episode_dir: Path,
    settings: Settings,
) -> tuple[Path | None, bool]:
    """Pick the cookie jar for this download, and say whether we own it.

    An operator-supplied jar wins, since it is the only way to reach
    members-only or age-gated media, and it is never ours to delete. Otherwise
    Bilibili gets a throwaway anonymous fingerprint, written per episode
    because yt-dlp rewrites the jar on exit and concurrent jobs must not share
    one.
    """
    if settings.YTDLP_COOKIEFILE is not None:
        return settings.YTDLP_COOKIEFILE, False
    if not (_is_bilibili(url) and settings.BILIBILI_ANONYMOUS_COOKIES):
        return None, False
    cookies = _bilibili_session.anonymous_cookies()
    if not cookies:
        return None, False
    path = episode_dir / "cookies.bilibili.txt"
    _bilibili_session.write_cookiefile(path, cookies)
    return path, True


def _is_bilibili(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in BILIBILI_HOSTS)


def _clear_partial_downloads(episode_dir: Path) -> None:
    for path in episode_dir.glob("audio.original.*"):
        path.unlink(missing_ok=True)


def _is_retryable(exc: Exception) -> bool:
    """A throttled host or a dropped connection is worth another attempt."""
    message = str(exc)
    if _RESTRICTED_PATTERN.search(message):
        return False
    return bool(_THROTTLED_PATTERN.search(message) or _TRANSIENT_PATTERN.search(message))


def _video_error_message(exc: Exception) -> str:
    message = str(exc)
    if _RESTRICTED_PATTERN.search(message):
        return "Video link is restricted or requires login"
    if _THROTTLED_PATTERN.search(message):
        return "Video host is throttling anonymous requests; please retry shortly"
    return "Video link could not be resolved"


async def _write_upload(upload: UploadLike, out_path: Path) -> int:
    total = 0
    with out_path.open("wb") as handle:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise PayloadTooLarge("audio file exceeds 1 GB limit")
            handle.write(chunk)
    if total == 0:
        raise UnsupportedMedia("empty upload")
    return total


async def _write_response_stream(response: httpx.Response, out_path: Path) -> int:
    total = 0
    with out_path.open("wb") as handle:
        async for chunk in response.aiter_bytes():
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise PayloadTooLarge("audio file exceeds 1 GB limit")
            handle.write(chunk)
    if total == 0:
        raise UnsupportedMedia("empty response")
    return total


def _validate_audio_content_type(content_type: str | None) -> None:
    if content_type is None or not content_type.lower().split(";", 1)[0].strip().startswith("audio/"):
        raise UnsupportedMedia("direct URL did not return an audio Content-Type")


def _detect_audio_ext(path: Path) -> str:
    header = path.read_bytes()[:64]
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0):
        return "mp3"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "wav"
    if header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand in {b"M4A ", b"mp42", b"isom", b"qt  "}:
            return "m4a"
    raise UnsupportedMedia("unsupported audio magic bytes")


async def _probe_duration_seconds(path: Path) -> int:
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        "format=duration",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise UnsupportedMedia(stderr.decode("utf-8", errors="replace").strip())
    payload = json.loads(stdout.decode("utf-8"))
    duration = float(payload["format"]["duration"])
    return int(round(duration))


async def _run_ffmpeg_normalize(in_path: Path, out_path: Path) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(in_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(out_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise UnsupportedMedia(stderr.decode("utf-8", errors="replace").strip())
