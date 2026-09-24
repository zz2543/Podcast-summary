from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

import pytest
import yt_dlp

from podsum.config import Settings
from podsum.services import _bilibili_session
from podsum.services.ingest import (
    UnsupportedMedia,
    _download_video_audio,
    _is_bilibili,
    _video_error_message,
    extract_url,
    normalize_video_url,
)

BILIBILI_URL = "https://www.bilibili.com/video/BV1XV411o7ra"
YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

THROTTLED_ERROR = (
    "ERROR: [BiliBili] 1XV411o7ra: Unable to download webpage: "
    "HTTP Error 412: Precondition Failed"
)


def _settings(tmp_path: Path, **overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        DATA_DIR=tmp_path / "data",
        DB_PATH=tmp_path / "podsum.sqlite3",
        ASR_PROVIDER="openai_whisper",
        LLM_PROVIDER="anthropic",
        TTS_PROVIDER="qwen",
        OPENAI_API_KEY="openai",
        ANTHROPIC_API_KEY="anthropic",
        ANTHROPIC_MODEL="claude-test",
        DASHSCOPE_API_KEY="dashscope",
        YTDLP_RETRY_DELAY_SECONDS=0.0,
        **overrides,
    )


class _FakeYoutubeDL:
    """Records the options each YoutubeDL instance was built with."""

    calls: list[dict[str, object]] = []
    errors: list[str | None] = []

    def __init__(self, options: dict[str, object]) -> None:
        self.options = options
        type(self).calls.append(dict(options))

    def __enter__(self) -> _FakeYoutubeDL:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def extract_info(self, url: str, *, download: bool) -> dict[str, object]:
        assert download is True
        attempt = len(type(self).calls) - 1
        if attempt < len(type(self).errors) and type(self).errors[attempt] is not None:
            raise yt_dlp.utils.DownloadError(type(self).errors[attempt])
        outtmpl = str(self.options["outtmpl"])
        produced = Path(outtmpl.replace("%(ext)s", "mp3"))
        produced.write_bytes(b"fake audio")
        return {"id": "x", "title": "Test video", "duration": 12}


@pytest.fixture(autouse=True)
def _fake_ytdl(monkeypatch: Any) -> None:
    _FakeYoutubeDL.calls = []
    _FakeYoutubeDL.errors = []
    _bilibili_session.reset_cache()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    monkeypatch.setattr(
        _bilibili_session, "anonymous_cookies", lambda: {"buvid3": "B3", "buvid4": "B4"}
    )


def test_download_never_reads_browser_cookies(tmp_path: Path) -> None:
    _download_video_audio(YOUTUBE_URL, tmp_path, _settings(tmp_path))

    assert "cookiesfrombrowser" not in _FakeYoutubeDL.calls[0]


def test_youtube_download_sends_no_cookiefile(tmp_path: Path) -> None:
    _download_video_audio(YOUTUBE_URL, tmp_path, _settings(tmp_path))

    options = _FakeYoutubeDL.calls[0]
    assert "cookiefile" not in options
    assert "http_headers" not in options
    assert options["format"] == "bestaudio/best"


def test_bilibili_download_sends_referer_and_anonymous_fingerprint(tmp_path: Path) -> None:
    _download_video_audio(BILIBILI_URL, tmp_path, _settings(tmp_path))

    options = _FakeYoutubeDL.calls[0]
    assert options["http_headers"] == {"Referer": _bilibili_session.REFERER}
    cookiefile = Path(str(options["cookiefile"]))
    assert cookiefile.parent == tmp_path


def test_anonymous_cookiefile_is_removed_after_download(tmp_path: Path) -> None:
    _download_video_audio(BILIBILI_URL, tmp_path, _settings(tmp_path))

    cookiefile = Path(str(_FakeYoutubeDL.calls[0]["cookiefile"]))
    assert not cookiefile.exists()


def test_configured_cookiefile_wins_over_anonymous_fingerprint(tmp_path: Path) -> None:
    operator_jar = tmp_path / "operator-cookies.txt"
    operator_jar.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    settings = _settings(tmp_path, YTDLP_COOKIEFILE=operator_jar)

    _download_video_audio(BILIBILI_URL, tmp_path, settings)

    assert _FakeYoutubeDL.calls[0]["cookiefile"] == str(operator_jar)
    assert operator_jar.exists(), "an operator-supplied jar must not be deleted"


def test_bilibili_download_skips_cookies_when_disabled(tmp_path: Path) -> None:
    settings = _settings(tmp_path, BILIBILI_ANONYMOUS_COOKIES=False)

    _download_video_audio(BILIBILI_URL, tmp_path, settings)

    assert "cookiefile" not in _FakeYoutubeDL.calls[0]


def test_throttled_download_is_retried_until_it_succeeds(tmp_path: Path) -> None:
    _FakeYoutubeDL.errors = [THROTTLED_ERROR, THROTTLED_ERROR, None]

    info, path = _download_video_audio(BILIBILI_URL, tmp_path, _settings(tmp_path))

    assert len(_FakeYoutubeDL.calls) == 3, "each retry needs a fresh YoutubeDL"
    assert info["title"] == "Test video"
    assert path.read_bytes() == b"fake audio"


def test_throttled_download_gives_up_after_max_attempts(tmp_path: Path) -> None:
    settings = _settings(tmp_path, YTDLP_MAX_ATTEMPTS=3)
    _FakeYoutubeDL.errors = [THROTTLED_ERROR] * 3

    with pytest.raises(yt_dlp.utils.DownloadError):
        _download_video_audio(BILIBILI_URL, tmp_path, settings)

    assert len(_FakeYoutubeDL.calls) == 3


def test_restricted_download_is_not_retried(tmp_path: Path) -> None:
    _FakeYoutubeDL.errors = ["ERROR: Sign in to confirm your age"]

    with pytest.raises(yt_dlp.utils.DownloadError):
        _download_video_audio(YOUTUBE_URL, tmp_path, _settings(tmp_path))

    assert len(_FakeYoutubeDL.calls) == 1, "a login wall must fail fast"


def test_throttle_is_not_reported_as_a_login_problem() -> None:
    # "webpage" contains the substring "age"; a naive check misfiled every
    # throttled Bilibili fetch as an authentication failure.
    message = _video_error_message(yt_dlp.utils.DownloadError(THROTTLED_ERROR))

    assert "throttling" in message
    assert "login" not in message


def test_login_walls_are_still_reported_as_such() -> None:
    for raw in (
        "ERROR: Sign in to confirm you're not a bot",
        "ERROR: This video is age-restricted",
        "ERROR: This video is private video content",
        "ERROR: members-only content",
    ):
        assert _video_error_message(yt_dlp.utils.DownloadError(raw)) == (
            "Video link is restricted or requires login"
        )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.bilibili.com/video/BV1", True),
        ("https://bilibili.com/video/BV1", True),
        ("https://m.bilibili.com/video/BV1", True),
        ("https://b23.tv/abcdef", True),
        ("https://www.youtube.com/watch?v=x", False),
        ("https://bilibili.com.attacker.example/video/BV1", False),
        ("https://notbilibili.com/video/BV1", False),
    ],
)
def test_bilibili_host_detection(url: str, expected: bool) -> None:
    assert _is_bilibili(url) is expected


def test_missing_output_file_is_reported(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        _FakeYoutubeDL,
        "extract_info",
        lambda self, url, *, download: {"id": "x", "title": "t"},
    )

    with pytest.raises(UnsupportedMedia, match="produced no file"):
        _download_video_audio(YOUTUBE_URL, tmp_path, _settings(tmp_path))


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_cookiefile_setting_is_treated_as_unset(
    tmp_path: Path, monkeypatch: Any, blank: str
) -> None:
    # A `YTDLP_COOKIEFILE=` line in .env would otherwise become Path("."),
    # which yt-dlp then tries to read as a cookie jar.
    monkeypatch.setenv("YTDLP_COOKIEFILE", blank)

    settings = _settings(tmp_path)

    assert settings.YTDLP_COOKIEFILE is None
    _download_video_audio(YOUTUBE_URL, tmp_path, settings)
    assert "cookiefile" not in _FakeYoutubeDL.calls[0]


BILIBILI_SHARE_TEXT = (
    "【OpenAI Images 2.5 实测：AI已经开始伪造我的记忆了。】"
    "https://www.bilibili.com/video/BV14dYx6iEwC"
    "?vd_source=e352aac32a47b1119609e13d767313f9"
)


@pytest.mark.parametrize(
    ("pasted", "expected"),
    [
        (BILIBILI_SHARE_TEXT, "https://www.bilibili.com/video/BV14dYx6iEwC"),
        (
            "【标题】 https://b23.tv/AbCdEf 快来看",
            "https://b23.tv/AbCdEf",
        ),
        (
            "https://www.bilibili.com/video/BV1XV411o7ra",
            "https://www.bilibili.com/video/BV1XV411o7ra",
        ),
        # A multi-part index and a start offset describe the media, so they stay.
        (
            "看这个 https://www.bilibili.com/video/BV1XV411o7ra?p=3&t=90&spm_id_from=333.999",
            "https://www.bilibili.com/video/BV1XV411o7ra?p=3&t=90",
        ),
        (
            "https://youtu.be/dQw4w9WgXcQ?si=T0kEn123",
            "https://youtu.be/dQw4w9WgXcQ",
        ),
        (
            "分享给你（https://www.bilibili.com/video/BV1XV411o7ra），记得看。",
            "https://www.bilibili.com/video/BV1XV411o7ra",
        ),
        (
            "Watch https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=shared.",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
    ],
)
def test_pasted_share_text_normalises_to_a_bare_url(pasted: str, expected: str) -> None:
    assert normalize_video_url(pasted) == expected


def test_two_shares_of_one_video_normalise_identically() -> None:
    # The episode dedupe index keys on source_ref, so per-sharer tracking
    # parameters would otherwise let the same video in twice.
    first = normalize_video_url(BILIBILI_SHARE_TEXT)
    second = normalize_video_url(
        "【同一个视频】https://www.bilibili.com/video/BV14dYx6iEwC?vd_source=deadbeef"
    )

    assert first == second


def test_text_without_a_url_is_passed_through_for_validation() -> None:
    assert normalize_video_url("  这不是链接  ") == "这不是链接"


def test_direct_url_extraction_keeps_the_query_string() -> None:
    # Presigned links carry their credentials in the query.
    presigned = "https://bucket.example.com/a.mp3?X-Amz-Signature=abc&X-Amz-Expires=900"

    assert extract_url(f"音频在这里 {presigned}") == presigned


SSL_ERROR = (
    "ERROR: [download] Got error: [SSL: UNEXPECTED_EOF_WHILE_READING] "
    "EOF occurred in violation of protocol (_ssl.c:1032)"
)


def test_dropped_connection_mid_download_is_retried(tmp_path: Path) -> None:
    # A long audio fetch drops often enough that this cannot be a hard failure.
    _FakeYoutubeDL.errors = [SSL_ERROR, None]

    info, _ = _download_video_audio(BILIBILI_URL, tmp_path, _settings(tmp_path))

    assert len(_FakeYoutubeDL.calls) == 2
    assert info["title"] == "Test video"


def test_permanently_unavailable_video_is_not_retried(tmp_path: Path) -> None:
    _FakeYoutubeDL.errors = ["ERROR: Video unavailable"] * 5

    with pytest.raises(yt_dlp.utils.DownloadError):
        _download_video_audio(YOUTUBE_URL, tmp_path, _settings(tmp_path))

    assert len(_FakeYoutubeDL.calls) == 1


def test_a_login_wall_is_never_retried_even_if_it_mentions_a_timeout(tmp_path: Path) -> None:
    _FakeYoutubeDL.errors = ["ERROR: Sign in to confirm your age (connection reset)"] * 5

    with pytest.raises(yt_dlp.utils.DownloadError):
        _download_video_audio(YOUTUBE_URL, tmp_path, _settings(tmp_path))

    assert len(_FakeYoutubeDL.calls) == 1


def test_ingest_reuses_an_existing_episode_dir_and_keeps_its_summary(tmp_path) -> None:
    from podsum.services.ingest import _claim_episode_dir, _discard_ingest

    episode_dir = tmp_path / "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    assert _claim_episode_dir(episode_dir) is True
    (episode_dir / "summary.md").write_text("from the first run")
    assert _claim_episode_dir(episode_dir) is False

    (episode_dir / "audio.original.webm.part").write_bytes(b"half")
    _discard_ingest(episode_dir, created_dir=False)
    assert sorted(p.name for p in episode_dir.iterdir()) == ["summary.md"]

    _discard_ingest(episode_dir, created_dir=True)
    assert not episode_dir.exists()
