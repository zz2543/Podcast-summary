from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest

from podsum.services import cover


@pytest.fixture
def png_bytes(tmp_path: Path) -> bytes:
    source = tmp_path / "source.png"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=1280x720",
         "-frames:v", "1", str(source)],
        check=True,
    )
    return source.read_bytes()


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch):
    """Route cover downloads to a table of url -> (status, body)."""
    routes: dict[str, tuple[int, bytes]] = {}
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status, body = routes.get(str(request.url), (404, b""))
        return httpx.Response(status, content=body)

    real_client = httpx.Client

    def client(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(cover.httpx, "Client", client)
    return routes, seen


def test_candidates_put_the_chosen_thumbnail_first_then_best_listed() -> None:
    info = {
        "thumbnail": "http://i0.hdslb.com/bfs/archive/a.jpg",
        "thumbnails": [
            {"url": "https://i.ytimg.com/vi/x/default.jpg", "preference": -10},
            {"url": "https://i.ytimg.com/vi/x/maxresdefault.jpg", "preference": 0},
            {"url": "https://i.ytimg.com/vi/x/hqdefault.jpg", "preference": -3},
            {"id": "no url"},
        ],
    }

    assert cover.thumbnail_urls(info) == [
        # Bilibili reports http://; it is fetched over https.
        "https://i0.hdslb.com/bfs/archive/a.jpg",
        "https://i.ytimg.com/vi/x/maxresdefault.jpg",
        "https://i.ytimg.com/vi/x/hqdefault.jpg",
        "https://i.ytimg.com/vi/x/default.jpg",
    ]


def test_no_thumbnail_means_no_candidates() -> None:
    assert cover.thumbnail_urls({"title": "x"}) == []


def test_a_missing_best_size_falls_back_to_the_next(tmp_path: Path, png_bytes: bytes, fake_http) -> None:
    routes, seen = fake_http
    routes["https://img/hq.jpg"] = (200, png_bytes)

    saved = cover.save_first_cover(
        ["https://img/maxres.jpg", "https://img/hq.jpg"], tmp_path, referer="https://www.bilibili.com/"
    )

    assert saved == tmp_path / "cover.jpg"
    assert saved.read_bytes()[:2] == b"\xff\xd8"  # re-encoded as JPEG
    assert [str(r.url) for r in seen] == ["https://img/maxres.jpg", "https://img/hq.jpg"]
    assert seen[0].headers["Referer"] == "https://www.bilibili.com/"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cover.jpg", "source.png"]


def test_an_undecodable_image_leaves_nothing_behind(tmp_path: Path, fake_http) -> None:
    routes, _ = fake_http
    routes["https://img/bad.jpg"] = (200, b"<html>not an image</html>")
    episode_dir = tmp_path / "episode"
    episode_dir.mkdir()

    assert cover.save_first_cover(["https://img/bad.jpg"], episode_dir) is None
    assert list(episode_dir.iterdir()) == []
