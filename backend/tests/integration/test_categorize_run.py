"""On-demand AI categorisation: runs, proposals and apply (feature 004 US3/US4)."""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

from _categories_fixtures import Ep, build_app, ulid
from fastapi.testclient import TestClient
from pydantic import BaseModel

from podsum.domain.categorizer import AssignPayload, TaxonomyPayload

_LABELLED_TITLE = re.compile(r"^(e\d+) (.+)$", re.MULTILINE)


class FakeLLM:
    """Answers the two categorisation prompts from fixed rules.

    `taxonomy` is phase A's reply. `rules` maps a title to a category name; the
    fake answers phase B with names, which the parser accepts like labels.
    """

    def __init__(
        self,
        taxonomy: dict[str, Any] | Exception,
        rules: dict[str, str | None],
        *,
        fail_batches: set[int] | None = None,
        gate: threading.Event | None = None,
    ) -> None:
        self.taxonomy = taxonomy
        self.rules = rules
        self.fail_batches = fail_batches or set()
        self.gate = gate
        self.prompts: list[str] = []
        self.assign_calls = 0

    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        self.prompts.append(prompt)
        if self.gate is not None:
            self.gate.wait(timeout=5)
        if schema is TaxonomyPayload:
            if isinstance(self.taxonomy, Exception):
                raise self.taxonomy
            return self.taxonomy
        assert schema is AssignPayload
        self.assign_calls += 1
        if self.assign_calls in self.fail_batches:
            raise RuntimeError("provider timed out")
        episodes = prompt.split("Episodes:", 1)[1]
        return {
            "assignments": [
                {"episode": label, "category": self.rules.get(title.strip())}
                for label, title in _LABELLED_TITLE.findall(episodes)
            ]
        }


def _app(tmp_path: Path, episodes: list[Ep], llm: FakeLLM, **kwargs: Any) -> Any:
    app = build_app(tmp_path, episodes, **kwargs)
    app.state.llm_client = llm
    return app


def _wait(client: TestClient, run_id: str, *, until: tuple[str, ...] = ("ready", "failed", "cancelled")) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        body = client.get(f"/api/categorize/{run_id}").json()
        if body["state"] in until:
            return body
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish: {body}")


def _run(client: TestClient) -> dict[str, Any]:
    started = client.post("/api/categorize")
    assert started.status_code == 202, started.text
    return _wait(client, started.json()["run_id"])


def _category(client: TestClient, name: str) -> str:
    return client.post("/api/categories", json={"name": name}).json()["id"]


def _episode(client: TestClient, episode_id: str) -> dict[str, Any]:
    return client.get(f"/api/episodes/{episode_id}").json()


LIBRARY = [
    Ep(ulid(1), "Claude Code 入门", chapters=["安装", "第一个项目"], entities=["Claude Code"]),
    Ep(ulid(2), "Codex 全攻略", chapters=["配置"], entities=["Codex"]),
    Ep(ulid(3), "基金定投怎么做"),
    Ep(ulid(4), "资产配置入门"),
]
RULES: dict[str, str | None] = {
    "Claude Code 入门": "AI 编程",
    "Codex 全攻略": "AI 编程",
    "基金定投怎么做": "理财",
    "资产配置入门": "理财",
}
TAXONOMY = {"new_categories": [{"name": "AI 编程", "reason": "编程工具"}, {"name": "理财", "reason": "投资"}]}


def test_two_phases_produce_a_proposal_without_writing(tmp_path: Path) -> None:
    llm = FakeLLM(TAXONOMY, RULES)
    with TestClient(_app(tmp_path, LIBRARY, llm)) as client:
        body = _run(client)

        assert body["state"] == "ready"
        assert body["progress"] == {"done": 2, "total": 2}
        proposal = body["proposal"]
        assert [c["name"] for c in proposal["categories"]] == ["AI 编程", "理财"]
        assert all(c["is_new"] for c in proposal["categories"])
        assert len(proposal["changes"]) == 4
        assert proposal["skipped"] == {"categorized": 0, "locked": 0, "no_summary": 0, "no_suggestion": 0}

        # The prompts carry labels, digests and the library language — never ids.
        taxonomy_prompt, assign_prompt = llm.prompts
        assert "e1 Claude Code 入门 — 一句话总结" in taxonomy_prompt
        assert "Simplified Chinese" in taxonomy_prompt
        assert "chapters: 安装; 第一个项目" in assign_prompt
        assert "mentions: Claude Code" in assign_prompt
        assert ulid(1) not in taxonomy_prompt + assign_prompt

        # Nothing is written until the user applies (SC-003).
        assert client.get("/api/categories").json() == {"items": [], "uncategorized_count": 4}


def test_apply_writes_kept_suggestions_as_auto(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES))) as client:
        proposal = _run(client)["proposal"]
        keys = {c["name"]: c["key"] for c in proposal["categories"]}
        kept = [c for c in proposal["changes"] if c["episode_id"] != ulid(4)]  # user unticked one

        response = client.post(
            "/api/categories/apply",
            json={
                "new_categories": [
                    {"key": keys["AI 编程"], "name": "AI 工具"},  # renamed in the preview
                    {"key": keys["理财"], "name": "理财"},
                ],
                "assignments": [
                    {"episode_id": c["episode_id"], "from_category_id": None, "to_key": c["to_key"]}
                    for c in kept
                ],
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["applied"] == 3 and result["skipped"] == []
        assert [(c["name"], c["reused"]) for c in result["created"]] == [("AI 工具", False), ("理财", False)]

        assert _episode(client, ulid(1))["category"]["name"] == "AI 工具"
        assert _episode(client, ulid(1))["category_origin"] == "auto"
        assert _episode(client, ulid(4))["category"] is None
        listing = client.get("/api/categories").json()
        assert [(c["name"], c["origin"], c["episode_count"]) for c in listing["items"]] == [
            ("AI 工具", "ai", 2),
            ("理财", "ai", 1),
        ]


def test_manual_videos_are_never_proposed_or_overwritten(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES))) as client:
        mine = _category(client, "我的")
        client.put(f"/api/episodes/{ulid(1)}/category", json={"category_id": mine})
        # Taken out by hand: stays in Uncategorized, but AI must not file it.
        client.put(f"/api/episodes/{ulid(2)}/category", json={"category_id": None})

        proposal = _run(client)["proposal"]
        proposed = {c["episode_id"] for c in proposal["changes"]}
        assert ulid(1) not in proposed and ulid(2) not in proposed
        assert proposal["skipped"]["categorized"] == 1
        assert proposal["skipped"]["locked"] == 1

        # A crafted apply for a locked video is refused server-side (SC-002).
        result = client.post(
            "/api/categories/apply",
            json={
                "new_categories": [],
                "assignments": [{"episode_id": ulid(2), "from_category_id": None, "to_key": f"c:{mine}"}],
            },
        ).json()
        assert result["skipped"] == [{"episode_id": ulid(2), "reason": "locked"}]
        assert _episode(client, ulid(2))["category"] is None


def test_only_uncategorized_videos_take_part(tmp_path: Path) -> None:
    """A run files what is still Uncategorized, into an existing category or a
    new one. Videos already in a category — AI-filed ones included — stay put."""
    llm = FakeLLM({"new_categories": [{"name": "理财"}]}, RULES)
    with TestClient(_app(tmp_path, LIBRARY, llm)) as client:
        ai = _category(client, "AI 编程")
        client.post(
            "/api/categories/apply",
            json={
                "new_categories": [],
                "assignments": [{"episode_id": ulid(1), "from_category_id": None, "to_key": f"c:{ai}"}],
            },
        )
        assert _episode(client, ulid(1))["category_origin"] == "auto"

        proposal = _run(client)["proposal"]
        by_episode = {c["episode_id"]: c["to_key"] for c in proposal["changes"]}
        assert ulid(1) not in by_episode
        assert by_episode[ulid(2)] == f"c:{ai}"  # into an existing category
        assert proposal["skipped"]["categorized"] == 1
        new = next(c for c in proposal["categories"] if c["is_new"])
        assert new["name"] == "理财" and by_episode[ulid(3)] == new["key"]  # into a new one
        # The model never saw the filed video.
        assert "Claude Code 入门" not in "".join(llm.prompts)


def test_unsummarised_and_orphaned_rows_do_not_take_part(tmp_path: Path) -> None:
    episodes = [*LIBRARY, Ep(ulid(5), "还在跑", hook=None, status="processing"), Ep(ulid(6), "空总结", hook="  ")]
    llm = FakeLLM(TAXONOMY, RULES)
    with TestClient(_app(tmp_path, episodes, llm, orphan_hooks=3)) as client:
        proposal = _run(client)["proposal"]
        assert proposal["skipped"]["no_summary"] == 2
        assert "孤儿" not in llm.prompts[0]
        assert "e5" not in llm.prompts[0]


def test_one_failed_batch_leaves_the_rest_usable(tmp_path: Path) -> None:
    # 10 episodes in batches of 5: two batches, the first of which fails.
    many = [*LIBRARY, *(Ep(ulid(10 + n), f"基金定投怎么做 {n}") for n in range(6))]
    llm = FakeLLM(TAXONOMY, dict(RULES, **{f"基金定投怎么做 {n}": "理财" for n in range(6)}), fail_batches={1})
    with TestClient(_app(tmp_path, many, llm, CATEGORIZE_BATCH_SIZE=5)) as client:
        body = _run(client)
        assert body["state"] == "ready"
        assert body["progress"] == {"done": 3, "total": 3}
        assert body["proposal"]["failed_batches"] == 1
        assert body["proposal"]["skipped"]["no_suggestion"] == 5
        assert len(body["proposal"]["changes"]) == 5


def test_every_batch_failing_fails_the_run(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES, fail_batches={1}))) as client:
        body = _run(client)
        assert body["state"] == "failed"
        assert body["error"] == "every assignment batch failed"


def test_a_failed_taxonomy_fails_the_run(tmp_path: Path) -> None:
    for taxonomy, message in [
        (RuntimeError("provider is down"), "provider is down"),
        ({"new_categories": [{"name": "全部"}]}, "no_taxonomy"),
    ]:
        with TestClient(_app(tmp_path / message, LIBRARY, FakeLLM(taxonomy, RULES))) as client:
            body = _run(client)
            assert (body["state"], body["error"]) == ("failed", message)


def test_cancel_discards_the_run_and_a_second_start_is_refused(tmp_path: Path) -> None:
    gate = threading.Event()
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES, gate=gate))) as client:
        run_id = client.post("/api/categorize").json()["run_id"]

        again = client.post("/api/categorize")
        assert again.status_code == 409
        assert again.json()["error"]["details"] == {"run_id": run_id}

        assert client.delete(f"/api/categorize/{run_id}").json() == {"state": "cancelled"}
        gate.set()
        time.sleep(0.1)
        body = client.get(f"/api/categorize/{run_id}").json()
        assert body["state"] == "cancelled" and body["proposal"] is None
        assert client.get("/api/categories").json()["items"] == []

        # A cancelled run no longer blocks a new one.
        assert client.post("/api/categorize").status_code == 202
        assert client.delete("/api/categorize/nope").status_code == 404
        assert client.get("/api/categorize/nope").status_code == 404


def test_nothing_to_categorize(tmp_path: Path) -> None:
    llm = FakeLLM(TAXONOMY, RULES)
    with TestClient(_app(tmp_path, [Ep(ulid(1), "在跑", hook=None, status="processing")], llm)) as client:
        response = client.post("/api/categorize")
        assert response.status_code == 400
        assert "summary" in response.json()["error"]["message"]
    with TestClient(_app(tmp_path / "locked", [Ep(ulid(1), "锁了")], llm)) as client:
        client.put(f"/api/episodes/{ulid(1)}/category", json={"category_id": None})
        assert "by hand" in client.post("/api/categorize").json()["error"]["message"]


def test_apply_skips_rows_that_changed_since_the_proposal(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES))) as client:
        gone = _category(client, "将被删除")
        other = _category(client, "别处")
        proposal = _run(client)["proposal"]
        key = proposal["categories"][0]["key"]

        # After the proposal: one video moved by hand, one deleted.
        client.put(f"/api/episodes/{ulid(2)}/category", json={"category_id": other})
        client.delete(f"/api/episodes/{ulid(3)}")
        client.delete(f"/api/categories/{gone}")

        result = client.post(
            "/api/categories/apply",
            json={
                "new_categories": [
                    {"key": key, "name": " ai 编程 "},  # same name as an existing one: reused
                    {"key": "n:9", "name": "没人用"},  # rejected by the user: not referenced
                ],
                "assignments": [
                    {"episode_id": ulid(1), "from_category_id": None, "to_key": key},
                    {"episode_id": ulid(2), "from_category_id": None, "to_key": key},
                    {"episode_id": ulid(3), "from_category_id": None, "to_key": key},
                    {"episode_id": ulid(4), "from_category_id": None, "to_key": f"c:{gone}"},
                ],
            },
        ).json()
        assert result["applied"] == 1
        assert result["skipped"] == [
            {"episode_id": ulid(2), "reason": "locked"},
            {"episode_id": ulid(3), "reason": "episode_gone"},
            {"episode_id": ulid(4), "reason": "category_gone"},
        ]
        names = [c["name"] for c in client.get("/api/categories").json()["items"]]
        assert "没人用" not in names


def test_apply_reuses_an_existing_category_with_the_same_name(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES))) as client:
        existing = _category(client, "AI 编程")
        result = client.post(
            "/api/categories/apply",
            json={
                "new_categories": [{"key": "n:1", "name": "ai 编程"}],
                "assignments": [{"episode_id": ulid(1), "from_category_id": None, "to_key": "n:1"}],
            },
        ).json()
        assert result["created"] == [{"key": "n:1", "category_id": existing, "name": "AI 编程", "reused": True}]
        assert result["applied"] == 1


def test_apply_changed_when_an_ai_managed_video_moved(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES))) as client:
        first = _category(client, "一")
        second = _category(client, "二")
        payload = {"new_categories": [], "assignments": [{"episode_id": ulid(1), "from_category_id": None, "to_key": f"c:{first}"}]}
        assert client.post("/api/categories/apply", json=payload).json()["applied"] == 1
        # The same stale suggestion again: the video is no longer where it was.
        payload["assignments"][0]["to_key"] = f"c:{second}"
        assert client.post("/api/categories/apply", json=payload).json()["skipped"] == [
            {"episode_id": ulid(1), "reason": "changed"}
        ]


def test_apply_rejects_malformed_bodies(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES))) as client:
        for body in [
            {"assignments": "x"},
            {"assignments": [{"episode_id": ulid(1)}]},
            {"new_categories": [{"key": "n:1"}], "assignments": []},
            {"new_categories": [{"key": "n:1", "name": "未分类"}], "assignments": []},
        ]:
            assert client.post("/api/categories/apply", json=body).status_code == 400


def test_release_lets_the_next_run_consider_the_video(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, LIBRARY, FakeLLM(TAXONOMY, RULES))) as client:
        client.put(f"/api/episodes/{ulid(1)}/category", json={"category_id": None})
        assert ulid(1) not in {c["episode_id"] for c in _run(client)["proposal"]["changes"]}

        client.post(f"/api/episodes/{ulid(1)}/category/release")
        assert ulid(1) in {c["episode_id"] for c in _run(client)["proposal"]["changes"]}


class _ProviderError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def test_provider_refusals_are_reported_as_codes(tmp_path: Path) -> None:
    """The client names these in plain words instead of showing the raw body."""
    cases = [
        (_ProviderError(402, "Error code: 402 - {'message': 'Insufficient Balance'}"), "llm_insufficient_balance"),
        (_ProviderError(429, "insufficient_quota"), "llm_insufficient_balance"),
        (_ProviderError(401, "Authentication Fails"), "llm_auth_failed"),
        (_ProviderError(429, "slow down"), "llm_rate_limited"),
    ]
    for index, (error, code) in enumerate(cases):
        with TestClient(_app(tmp_path / str(index), LIBRARY, FakeLLM(error, RULES))) as client:
            body = _run(client)
            assert (body["state"], body["error"]) == ("failed", code)


def test_a_provider_refusal_in_every_batch_is_named(tmp_path: Path) -> None:
    class BrokeAfterTaxonomy(FakeLLM):
        def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
            if schema is AssignPayload:
                raise _ProviderError(402, "Insufficient Balance")
            return super().complete_json(prompt, schema)

    with TestClient(_app(tmp_path, LIBRARY, BrokeAfterTaxonomy(TAXONOMY, RULES))) as client:
        assert _run(client)["error"] == "llm_insufficient_balance"
