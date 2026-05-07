from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.exporters.json_export import render
from podsum.persistence.models import Base, Chapter, Episode, Quote, SummaryArtifact, TranscriptSegment


def test_us2_quote_jump_math_preserves_quote_start_ms() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        episode = Episode(
            id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            source_type="local_file",
            source_ref="sample.mp3",
            title="Quote math",
            duration_seconds=120,
            language="en",
            status="done",
            created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
            data_dir="data/episode",
        )
        artifact = SummaryArtifact(
            episode_id=episode.id,
            hook="A useful hook",
            three_act={
                "background": "Context.",
                "core_argument": "Argument.",
                "conclusion": "Ending.",
            },
            stage_status={"hook": "present", "three_act": "present", "chapters": "present"},
            prompt_versions={},
        )
        segment = TranscriptSegment(
            episode_id=episode.id,
            idx=0,
            start_ms=90_000,
            end_ms=95_000,
            text="This quote starts at ninety seconds.",
            language="en",
        )
        chapter = Chapter(
            episode_id=episode.id,
            idx=0,
            title="Quote chapter",
            start_ms=80_000,
            end_ms=100_000,
            key_points=["A point"],
        )
        quote = Quote(
            chapter=chapter,
            idx=0,
            text="This quote starts at ninety seconds.",
            start_ms=90_000,
            verified=True,
        )
        session.add_all([episode, artifact, segment, chapter, quote])
        session.flush()

        output = render(
            {
                "episode": episode,
                "artifact": artifact,
                "chapters": [chapter],
                "entities": [],
            }
        )

    assert output["chapters"][0]["quotes"][0]["start_ms"] == 90_000
