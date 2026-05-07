from __future__ import annotations

import json
import time
import wave
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient
from jsonschema import validate
from sqlalchemy import create_engine

from podsum.config import Settings
from podsum.exporters.json_export import EPISODE_OUTPUT_SCHEMA
from podsum.main import create_app
from podsum.persistence.models import Base


def test_us1_end_to_end_upload_reaches_done(tmp_path: Path) -> None:
    db_path = tmp_path / "podsum.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    audio_path = tmp_path / "sample.wav"
    _write_wav(audio_path)
    settings = _settings(tmp_path, db_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=False) as router:
        router.post("https://api.openai.com/v1/audio/transcriptions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "text": "hello world",
                    "duration": 1.0,
                    "language": "english",
                    "segments": [
                        {
                            "id": 0,
                            "seek": 0,
                            "start": 0.0,
                            "end": 1.0,
                            "text": "hello world",
                            "tokens": [],
                            "temperature": 0.0,
                            "avg_logprob": 0.0,
                            "compression_ratio": 1.0,
                            "no_speech_prob": 0.0,
                        }
                    ],
                },
            )
        )
        router.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={"content": [{"type": "text", "text": '{"hook":"Why demos need focus"}'}]},
                ),
                httpx.Response(
                    200,
                    json={
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "background": "The episode opens with context.",
                                        "core_argument": "Focused demos reduce review time.",
                                        "conclusion": "Ship smaller and clearer summaries.",
                                    }
                                ),
                            }
                        ]
                    },
                ),
            ]
        )

        with TestClient(app) as client:
            with audio_path.open("rb") as audio:
                created = client.post(
                    "/api/episodes",
                    data={"source_type": "local_file"},
                    files={"file": ("sample.wav", audio, "audio/wav")},
                )
            assert created.status_code == 201
            episode_id = created.json()["episode"]["id"]
            job_id = created.json()["job"]["id"]

            job = _wait_for_job(client, job_id)
            assert job["state"] == "done"

            detail = client.get(f"/api/episodes/{episode_id}").json()
            assert detail["status"] == "done"
            assert detail["hook"] == "Why demos need focus"
            assert detail["three_act"]["background"]
            validate(instance=detail, schema=EPISODE_OUTPUT_SCHEMA)

            markdown = client.get(f"/api/episodes/{episode_id}/files/markdown")
            assert markdown.status_code == 200
            assert "Why demos need focus" in markdown.text


def _settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        DATA_DIR=tmp_path / "data",
        DB_PATH=db_path,
        ASR_PROVIDER="openai_whisper",
        LLM_PROVIDER="anthropic",
        VOLC_ACCESS_KEY_ID="ak",
        VOLC_SECRET_ACCESS_KEY="sk",
        OPENAI_API_KEY="openai",
        DEEPSEEK_API_KEY="deepseek",
        ANTHROPIC_API_KEY="anthropic",
        ANTHROPIC_MODEL="claude-test",
        DOUBAO_TTS_APP_ID="tts-app",
        DOUBAO_TTS_ACCESS_TOKEN="tts-token",
    )


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(b"\x00\x00" * 16_000)


def _wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()
        if payload["state"] in {"done", "partial", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("job did not finish")
