from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from jsonschema import Draft202012Validator, validate

from podsum.exporters.json_export import EPISODE_OUTPUT_SCHEMA, render


def test_us1_json_export_validates_against_contract_schema() -> None:
    output = render(
        {
            "episode": SimpleNamespace(
                id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                title="Episode title",
                podcast_name="Pod",
                guests=None,
                source_type="local_file",
                source_ref="sample.mp3",
                duration_seconds=120,
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
                    quotes=[SimpleNamespace(text="Verified quote.", start_ms=12_000, verified=True)],
                )
            ],
            "entities": [
                SimpleNamespace(
                    name="Ada Lovelace",
                    kind="person",
                    count=1,
                    sample_timestamps_ms=[12_000],
                )
            ],
        }
    )

    Draft202012Validator.check_schema(EPISODE_OUTPUT_SCHEMA)
    validate(instance=output, schema=EPISODE_OUTPUT_SCHEMA)
