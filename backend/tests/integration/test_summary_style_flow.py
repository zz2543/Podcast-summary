"""The submit-time summary style has to survive all the way to the LLM prompts."""

from __future__ import annotations

import json
import time
import wave
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base

NOTE = "lean on methodology, skip the anecdotes"


def test_style_reaches_every_summary_prompt(tmp_path: Path) -> None:
    prompts = _run_submission(
        tmp_path,
        data={
            "source_type": "local_file",
            "summary_style": "study_notes",
            "style_note": f"{NOTE}\nand ignore nothing",
        },
    )

    hook_prompt, three_act_prompt, usefulness_prompt, chapter_prompt = prompts["llm"][:4]
    for prompt in (hook_prompt, three_act_prompt, chapter_prompt):
        assert "Style directive" in prompt
        assert "someone taking study notes" in prompt
        # The note is collapsed onto one line before it is quoted into the prompt.
        assert f'"{NOTE} and ignore nothing"' in prompt

    # Scoring is deliberately style-free (FR-027): style changes how the summary
    # reads, not how valuable the episode is.
    assert "Style directive" not in usefulness_prompt

    detail = prompts["detail"]
    assert detail["summary_style"] == {
        "preset": "study_notes",
        "note": f"{NOTE} and ignore nothing",
        "detail": "standard",
    }
    assert detail["prompt_versions"]["one_liner"] == "v2"
    assert detail["prompt_versions"]["three_act"] == "v4"
    assert detail["prompt_versions"]["chapter_outline"] == "v3"
    assert detail["prompt_versions"]["summary_style"] == "v2"


def test_default_submission_carries_no_directive(tmp_path: Path) -> None:
    prompts = _run_submission(tmp_path, data={"source_type": "local_file"})

    for prompt in prompts["llm"][:4]:
        assert "Style directive" not in prompt

    detail = prompts["detail"]
    assert detail["summary_style"] == {"preset": "default", "note": None, "detail": "standard"}
    assert "summary_style" not in detail["prompt_versions"]


def test_unknown_preset_is_rejected(tmp_path: Path) -> None:
    audio_path, app = _fixture(tmp_path)
    with TestClient(app) as client, audio_path.open("rb") as audio:
        response = client.post(
            "/api/episodes",
            data={"source_type": "local_file", "summary_style": "hacker_mode"},
            files={"file": ("sample.wav", audio, "audio/wav")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def test_overlong_note_is_rejected(tmp_path: Path) -> None:
    audio_path, app = _fixture(tmp_path)
    with TestClient(app) as client, audio_path.open("rb") as audio:
        response = client.post(
            "/api/episodes",
            data={"source_type": "local_file", "style_note": "x" * 201},
            files={"file": ("sample.wav", audio, "audio/wav")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def test_json_submission_reads_style_fields(tmp_path: Path) -> None:
    # The endpoint declares Form parameters for the multipart variant; this keeps
    # the JSON variant honest about picking the style up from the body instead.
    _, app = _fixture(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/episodes",
            json={
                "source_type": "youtube",
                "source_ref": "https://www.youtube.com/watch?v=abcdefghijk",
                "summary_style": "hacker_mode",
            },
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def _run_submission(tmp_path: Path, *, data: dict[str, str]) -> dict:
    audio_path, app = _fixture(tmp_path)
    seen: list[str] = []

    with respx.mock(assert_all_called=False) as router:
        router.post("https://api.openai.com/v1/audio/transcriptions").mock(
            return_value=httpx.Response(200, json=_TRANSCRIPT)
        )
        router.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=_llm_recorder(seen)
        )

        with TestClient(app) as client:
            with audio_path.open("rb") as audio:
                created = client.post(
                    "/api/episodes",
                    data=data,
                    files={"file": ("sample.wav", audio, "audio/wav")},
                )
            assert created.status_code == 201, created.text
            episode_id = created.json()["episode"]["id"]
            job = _wait_for_job(client, created.json()["job"]["id"])
            assert job["state"] == "done", job
            detail = client.get(f"/api/episodes/{episode_id}").json()

    return {"llm": seen, "detail": detail}


def _llm_recorder(seen: list[str]):
    payloads = [
        {"hook": "Why demos need focus"},
        {
            "background": "The episode opens with context.",
            "core_argument": "Focused demos reduce review time.",
            "conclusion": "Ship smaller and clearer summaries.",
        },
        {"score": 78, "rationale": "Specific, verifiable claims about demo review time."},
        {
            "chapters": [
                {
                    "title": "Opening",
                    "key_points": ["The sample introduces the idea."],
                    "candidate_quotes": [{"text": "hello world", "start_ms": 0}],
                }
            ]
        },
        {"entities": [{"name": "world", "kind": "product", "count": 9}]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(
            "\n".join(
                part.get("text", "")
                for message in body.get("messages", [])
                for part in _content_parts(message)
            )
        )
        payload = payloads[min(len(seen) - 1, len(payloads) - 1)]
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": json.dumps(payload)}]}
        )

    return handler


def _content_parts(message: dict) -> list[dict]:
    content = message.get("content")
    if isinstance(content, str):
        return [{"text": content}]
    return [part for part in content or [] if isinstance(part, dict)]


def _fixture(tmp_path: Path) -> tuple[Path, object]:
    db_path = tmp_path / "podsum.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    audio_path = tmp_path / "sample.wav"
    with wave.open(str(audio_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(b"\x00\x00" * 16_000)

    return audio_path, create_app(_settings(tmp_path, db_path))


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


_TRANSCRIPT = {
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
}


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["state"] in {"done", "partial", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("job did not finish")
