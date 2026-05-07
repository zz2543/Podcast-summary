from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from podsum.exporters.json_export import EPISODE_OUTPUT_SCHEMA, render


def test_json_render_populates_us1_fields() -> None:
    output = render(
        {
            "episode": SimpleNamespace(
                id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                title="Episode title",
                podcast_name="Pod",
                guests=None,
                source_type="youtube",
                source_ref="https://example.test/watch",
                duration_seconds=125,
                language="en",
                status="done",
                created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
                updated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
            ),
            "artifact": SimpleNamespace(
                hook="A useful reason to listen",
                three_act={
                    "background": "Context.",
                    "core_argument": "Argument.",
                    "conclusion": "Ending.",
                },
                stage_status={"hook": "present", "three_act": "present"},
                prompt_versions={"one_liner": "v1", "three_act": "v1"},
                markdown_path="data/id/summary.md",
                json_path="data/id/summary.json",
                tts_path=None,
            ),
            "chapters": [
                SimpleNamespace(
                    idx=0,
                    title="Opening",
                    start_ms=0,
                    end_ms=65_000,
                    key_points=["Point one"],
                    quotes=[
                        SimpleNamespace(text="Verified quote.", start_ms=12_000, verified=True),
                        SimpleNamespace(text="Rejected quote.", start_ms=13_000, verified=False),
                    ],
                )
            ],
            "entities": [
                SimpleNamespace(
                    name="DeepSeek",
                    kind="product",
                    count=2,
                    sample_timestamps_ms=[0, 1_000, 2_000, 3_000, 4_000, 5_000],
                )
            ],
        }
    )

    assert EPISODE_OUTPUT_SCHEMA["title"] == "EpisodeOutput"
    assert output["hook"] == "A useful reason to listen"
    assert output["chapters"][0]["quotes"] == [{"text": "Verified quote.", "start_ms": 12_000}]
    assert output["entities"][0] == {
        "name": "DeepSeek",
        "kind": "product",
        "count": 2,
        "sample_timestamps_ms": [0, 1_000, 2_000, 3_000, 4_000],
    }
    assert output["stage_status"]["tts"] == "missing"
    assert output["prompt_versions"]["chapter_outline"] == "v1"
