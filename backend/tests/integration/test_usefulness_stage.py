"""FR-027: the usefulness stage scores an episode and degrades without taking it down."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import validate
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.exporters.json_export import EPISODE_OUTPUT_SCHEMA
from podsum.persistence.models import Base, Episode, Job, SummaryArtifact, TranscriptSegment
from podsum.services.pipeline import create_us1_pipeline

EPISODE_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
JOB_ID = "01BRZ3NDEKTSV4RRFFQ69G5FAV"


class FakeASRClient:
    def transcribe(self, audio_path: Any, language_hint: Any, audio_url: Any = None) -> list[Any]:
        raise AssertionError("the transcript is seeded; ASR must not run")


class FakeLLMClient:
    """Answers each stage by looking at the schema it was handed."""

    def __init__(self, *, usefulness: dict[str, Any] | Exception) -> None:
        self.usefulness = usefulness
        self.usefulness_calls = 0

    def complete_json(self, prompt: str, schema: Any) -> dict[str, Any]:
        del prompt
        if "score" in schema.model_fields:
            self.usefulness_calls += 1
            if isinstance(self.usefulness, Exception):
                raise self.usefulness
            return self.usefulness
        if "hook" in schema.model_fields:
            return {"hook": "Why cheap restarts change the cost model"}
        if "chapters" in schema.model_fields:
            return {
                "chapters": [
                    {
                        "title": "Opening",
                        "key_points": ["The sample introduces the idea."],
                        "candidate_quotes": [{"text": "hello world", "start_ms": 0}],
                    }
                ]
            }
        if "entities" in schema.model_fields:
            return {"entities": [{"name": "world", "kind": "product", "count": 1}]}
        return {
            "background": "The episode opens with context.",
            "core_argument": "Focused demos reduce review time.",
            "conclusion": "Ship smaller and clearer summaries.",
        }


def test_usefulness_score_is_stored_and_exported(tmp_path: Path) -> None:
    session, settings, job = _seeded_run(tmp_path)
    llm = FakeLLMClient(usefulness={"score": 78, "rationale": "Concrete, verifiable claims."})

    with session:
        pipeline = create_us1_pipeline(
            session, settings, asr_client=FakeASRClient(), llm_client=llm
        )
        asyncio.run(pipeline.run(job))
        session.commit()

        artifact = session.get(SummaryArtifact, EPISODE_ID)
        assert artifact is not None
        assert artifact.usefulness_score == 78
        assert artifact.usefulness_band == "worth_listening"
        assert artifact.usefulness_rationale == "Concrete, verifiable claims."
        assert artifact.stage_status["usefulness"] == "present"
        assert artifact.prompt_versions["usefulness_score"] == "v1"

        exported = json.loads(Path(artifact.json_path).read_text(encoding="utf-8"))

    validate(instance=exported, schema=EPISODE_OUTPUT_SCHEMA)
    assert exported["usefulness"] == {
        "score": 78,
        "band": "worth_listening",
        "rationale": "Concrete, verifiable claims.",
    }
    markdown = Path(artifact.markdown_path).read_text(encoding="utf-8")
    assert "## Usefulness" in markdown
    assert "78/100 · Worth listening · Concrete, verifiable claims." in markdown


def test_scoring_failure_leaves_the_rest_of_the_episode_usable(tmp_path: Path) -> None:
    session, settings, job = _seeded_run(tmp_path)
    llm = FakeLLMClient(usefulness=RuntimeError("scoring upstream is down"))

    with session:
        pipeline = create_us1_pipeline(
            session, settings, asr_client=FakeASRClient(), llm_client=llm
        )
        asyncio.run(pipeline.run(job))
        session.commit()

        finished = session.scalar(select(Job).where(Job.id == JOB_ID))
        assert finished is not None
        # Optional stage: the episode degrades to "partial", it does not fail.
        assert finished.state == "partial"

        artifact = session.get(SummaryArtifact, EPISODE_ID)
        assert artifact is not None
        assert artifact.stage_status["usefulness"] == "failed_after_retries"
        assert artifact.usefulness_score is None
        assert artifact.usefulness_band is None
        assert artifact.usefulness_rationale is None
        # The required artifacts are untouched.
        assert artifact.hook
        assert artifact.three_act

        exported = json.loads(Path(artifact.json_path).read_text(encoding="utf-8"))

    validate(instance=exported, schema=EPISODE_OUTPUT_SCHEMA)
    assert exported["usefulness"] is None
    assert exported["stage_status"]["usefulness"] == "failed_after_retries"
    assert "## Usefulness" not in Path(artifact.markdown_path).read_text(encoding="utf-8")
    assert llm.usefulness_calls > 1, "a failing optional stage should be retried"


def test_a_stale_score_is_cleared_when_a_rerun_fails(tmp_path: Path) -> None:
    session, settings, job = _seeded_run(tmp_path)

    with session:
        session.add(
            SummaryArtifact(
                episode_id=EPISODE_ID,
                usefulness_score=91,
                usefulness_band="must_listen",
                usefulness_rationale="From an earlier run.",
                stage_status={"usefulness": "present"},
                prompt_versions={"usefulness_score": "v1"},
            )
        )
        session.commit()

        pipeline = create_us1_pipeline(
            session,
            settings,
            asr_client=FakeASRClient(),
            llm_client=FakeLLMClient(usefulness=RuntimeError("still down")),
        )
        asyncio.run(pipeline.run(job))
        session.commit()

        artifact = session.get(SummaryArtifact, EPISODE_ID)
        assert artifact is not None
        assert artifact.usefulness_score is None
        assert artifact.usefulness_band is None
        assert artifact.usefulness_rationale is None


def _seeded_run(tmp_path: Path) -> tuple[Session, Settings, Job]:
    db_path = tmp_path / "podsum.sqlite3"
    episode_dir = tmp_path / "data" / EPISODE_ID
    episode_dir.mkdir(parents=True)
    (episode_dir / "audio.normalized.mp3").write_bytes(b"cached")

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Episode(
                    id=EPISODE_ID,
                    source_type="local_file",
                    source_ref="sample.wav",
                    title="Cached transcript episode",
                    duration_seconds=60,
                    language="en",
                    status="processing",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    data_dir=str(episode_dir),
                ),
                Job(
                    id=JOB_ID,
                    episode_id=EPISODE_ID,
                    state="transcribing",
                    stage_progress={"transcribe": {"status": "done"}},
                    attempt=1,
                ),
                TranscriptSegment(
                    episode_id=EPISODE_ID,
                    idx=0,
                    start_ms=0,
                    end_ms=1000,
                    text="hello world",
                    language="en",
                ),
            ]
        )
        session.commit()

    session = Session(engine)
    job = session.scalar(select(Job).where(Job.id == JOB_ID))
    assert job is not None
    return session, _settings(tmp_path, db_path), job


def _settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        DATA_DIR=tmp_path / "data",
        DB_PATH=db_path,
        VOLC_ACCESS_KEY_ID="ak",
        VOLC_SECRET_ACCESS_KEY="sk",
        DOUBAO_ASR_APP_ID="asr",
        DOUBAO_ASR_ACCESS_TOKEN="asr-token",
        DEEPSEEK_API_KEY="deepseek",
        DOUBAO_TTS_APP_ID="tts",
        DOUBAO_TTS_ACCESS_TOKEN="tts-token",
    )
