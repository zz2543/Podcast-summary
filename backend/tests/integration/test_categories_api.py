"""Manual categories: CRUD, ordering and per-episode assignment (feature 004 US1/US2/US4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _categories_fixtures import Ep, build_app, ulid
from fastapi.testclient import TestClient

A, B, C = ulid(1), ulid(2), ulid(3)


def _client(tmp_path: Path) -> TestClient:
    return TestClient(build_app(tmp_path, [Ep(A, "甲"), Ep(B, "乙"), Ep(C, "丙")]))


def _create(client: TestClient, name: str) -> dict[str, Any]:
    response = client.post("/api/categories", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _episode(client: TestClient, episode_id: str) -> dict[str, Any]:
    items = client.get("/api/episodes", params={"limit": 200}).json()["items"]
    return next(item for item in items if item["id"] == episode_id)


def test_create_appends_and_validates_names(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        first = _create(client, "投资")
        second = _create(client, "  历史 ")
        assert (first["position"], second["position"]) == (0, 1)
        assert second["name"] == "历史"
        assert first["episode_count"] == 0 and first["origin"] == "user"

        for bad, reason in [("  ", "empty"), ("字" * 31, "too_long"), ("未分类", "reserved")]:
            response = client.post("/api/categories", json={"name": bad})
            assert response.status_code == 400
            assert response.json()["error"]["details"]["reason"] == reason

        duplicate = client.post("/api/categories", json={"name": " 投资 "})
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["details"] == {"category_id": first["id"]}

        assert client.post("/api/categories", json={"name": 3}).status_code == 400


def test_manual_assignment_locks_and_shows_everywhere(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        invest = _create(client, "投资")

        response = client.put(f"/api/episodes/{A}/category", json={"category_id": invest["id"]})
        assert response.status_code == 200
        assert response.json() == {
            "category": {"id": invest["id"], "name": "投资"},
            "category_origin": "manual",
        }

        assert _episode(client, A)["category"] == {"id": invest["id"], "name": "投资"}
        assert _episode(client, B)["category"] is None
        detail = client.get(f"/api/episodes/{A}").json()
        assert detail["category"]["id"] == invest["id"] and detail["category_origin"] == "manual"

        listing = client.get("/api/categories").json()
        assert listing["items"][0]["episode_count"] == 1
        assert listing["uncategorized_count"] == 2

        # Taking it out by hand keeps it locked, now in Uncategorized.
        out = client.put(f"/api/episodes/{A}/category", json={"category_id": None}).json()
        assert out == {"category": None, "category_origin": "manual"}
        assert client.get("/api/categories").json()["uncategorized_count"] == 3


def test_assignment_errors(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        invest = _create(client, "投资")
        missing_episode = client.put(f"/api/episodes/{ulid(99)}/category", json={"category_id": invest["id"]})
        assert missing_episode.status_code == 404
        assert missing_episode.json()["error"]["details"] == {"missing": "episode"}
        missing_category = client.put(f"/api/episodes/{A}/category", json={"category_id": "nope"})
        assert missing_category.status_code == 404
        assert missing_category.json()["error"]["details"] == {"missing": "category"}
        assert client.put(f"/api/episodes/{A}/category", json={}).status_code == 400
        assert client.put(f"/api/episodes/{A}/category", json={"category_id": 5}).status_code == 400


def test_assignment_does_not_touch_episode_updated_at(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        before = _episode(client, A)["updated_at"]
        invest = _create(client, "投资")
        client.put(f"/api/episodes/{A}/category", json={"category_id": invest["id"]})
        assert _episode(client, A)["updated_at"] == before


def test_deleting_an_episode_updates_counts(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        invest = _create(client, "投资")
        client.put(f"/api/episodes/{A}/category", json={"category_id": invest["id"]})
        assert client.delete(f"/api/episodes/{A}").status_code == 204
        listing = client.get("/api/categories").json()
        assert listing["items"][0]["episode_count"] == 0
        assert listing["uncategorized_count"] == 2


# --------------------------------------------------------------------- US2


def test_rename(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        invest = _create(client, "投资")
        history = _create(client, "历史")
        client.put(f"/api/episodes/{A}/category", json={"category_id": invest["id"]})

        renamed = client.patch(f"/api/categories/{invest['id']}", json={"name": "理财"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "理财" and renamed.json()["episode_count"] == 1
        assert _episode(client, A)["category"]["name"] == "理财"

        # The same name in another case is not a clash with itself…
        assert client.patch(f"/api/categories/{invest['id']}", json={"name": "Money"}).status_code == 200
        assert client.patch(f"/api/categories/{invest['id']}", json={"name": "MONEY"}).status_code == 200
        # …but is one with another category.
        clash = client.patch(f"/api/categories/{history['id']}", json={"name": " money "})
        assert clash.status_code == 409
        assert client.patch(f"/api/categories/{history['id']}", json={"name": ""}).status_code == 400
        assert client.patch("/api/categories/nope", json={"name": "x"}).status_code == 404


def test_delete_releases_videos_and_unlocks_them(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        invest = _create(client, "投资")
        client.put(f"/api/episodes/{A}/category", json={"category_id": invest["id"]})
        client.put(f"/api/episodes/{B}/category", json={"category_id": invest["id"]})

        response = client.delete(f"/api/categories/{invest['id']}")
        assert response.status_code == 200 and response.json() == {"released": 2}

        for episode_id in (A, B):
            episode = _episode(client, episode_id)
            assert episode["category"] is None and episode["category_origin"] is None
        assert client.get("/api/categories").json() == {"items": [], "uncategorized_count": 3}
        assert client.delete(f"/api/categories/{invest['id']}").status_code == 404


def test_reorder(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        ids = [_create(client, name)["id"] for name in ("一", "二", "三")]
        response = client.put("/api/categories/order", json={"ids": [ids[2], ids[0], ids[1]]})
        assert response.status_code == 200
        assert [item["name"] for item in response.json()["items"]] == ["三", "一", "二"]
        assert [item["name"] for item in client.get("/api/categories").json()["items"]] == ["三", "一", "二"]

        for bad in ([ids[0], ids[1]], [*ids, "extra"], [ids[0], ids[0], ids[1]], "nope"):
            assert client.put("/api/categories/order", json={"ids": bad}).status_code == 400


# --------------------------------------------------------------------- US4


def test_release_hands_a_manual_video_back_to_ai(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        invest = _create(client, "投资")
        client.put(f"/api/episodes/{A}/category", json={"category_id": invest["id"]})
        client.put(f"/api/episodes/{B}/category", json={"category_id": None})

        placed = client.post(f"/api/episodes/{A}/category/release").json()
        assert placed == {"category": {"id": invest["id"], "name": "投资"}, "category_origin": "auto"}
        out = client.post(f"/api/episodes/{B}/category/release").json()
        assert out == {"category": None, "category_origin": None}
        # Not manual: nothing to do.
        untouched = client.post(f"/api/episodes/{C}/category/release").json()
        assert untouched == {"category": None, "category_origin": None}
        assert client.post(f"/api/episodes/{ulid(99)}/category/release").status_code == 404
