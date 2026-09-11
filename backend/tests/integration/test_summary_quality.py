"""Chinese episodes must stay Chinese, and chapters must land on real times."""

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

# Chinese speech with the English product names that used to make the ASR tag
# whole utterances `en`, the episode "mixed", and the summary English.
LINES = [
    "今天我们来讲讲如何使用 AI 写代码,你可以装个 Codex 或者 Cloud Code,直接发一个指令。",
    "环境搭建这一步是一次性的,先初始化 Git 仓库,再写一个 AGENTS.md 把规则定下来。",
    "最后一定要人工验证,因为 AI 自测覆盖不了交互体验和边界情况。",
]
ANCHORS = ["装个 Codex 或者 Cloud Code", "再写一个 AGENTS.md 把规则定下来", "因为 AI 自测覆盖不了交互体验"]


def test_chinese_episode_is_summarized_in_chinese(tmp_path: Path) -> None:
    result = _run(tmp_path, data={"source_type": "local_file"})

    for prompt in result["llm"]:
        assert "Simplified Chinese" in prompt
        assert " in mixed" not in prompt

    assert result["detail"]["language"] == "zh"


def test_chapters_get_their_own_time_range(tmp_path: Path) -> None:
    chapters = _run(tmp_path, data={"source_type": "local_file"})["detail"]["chapters"]

    assert len(chapters) == 3
    starts = [chapter["start_ms"] for chapter in chapters]
    # Before key moments anchored them, every chapter after the first shared the
    # last segmenter span, i.e. one identical range repeated.
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)
    assert starts[0] == 0
    for chapter in chapters:
        assert chapter["end_ms"] > chapter["start_ms"]


def test_key_moments_carry_takeaway_and_optional_summary(tmp_path: Path) -> None:
    chapters = _run(tmp_path, data={"source_type": "local_file"})["detail"]["chapters"]

    moments = [moment for chapter in chapters for moment in chapter["quotes"]]
    assert len(moments) == 3
    for moment in moments:
        # The anchor stays verbatim — it is what makes the timestamp trustworthy.
        assert any(moment["text"] in line for line in LINES)
        assert moment["takeaway"]

    assert chapters[0]["summary"] == "作者先说明为什么一条指令不够。"
    assert chapters[1]["summary"] is None


def test_detail_level_reaches_the_prompt(tmp_path: Path) -> None:
    result = _run(tmp_path, data={"source_type": "local_file", "detail_level": "detailed"})

    chapter_prompt = result["llm"][3]
    assert "Six to eight key points per chapter" in chapter_prompt
    assert result["detail"]["summary_style"]["detail"] == "detailed"
    assert result["detail"]["prompt_versions"]["summary_style"] == "v2"


def test_unknown_detail_level_is_rejected(tmp_path: Path) -> None:
    audio_path, app = _fixture(tmp_path)
    with TestClient(app) as client, audio_path.open("rb") as audio:
        response = client.post(
            "/api/episodes",
            data={"source_type": "local_file", "detail_level": "exhaustive"},
            files={"file": ("sample.wav", audio, "audio/wav")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def _run(tmp_path: Path, *, data: dict[str, str]) -> dict:
    audio_path, app = _fixture(tmp_path)
    seen: list[str] = []

    with respx.mock(assert_all_called=False) as router:
        router.post("https://api.openai.com/v1/audio/transcriptions").mock(
            return_value=httpx.Response(200, json=_transcript())
        )
        router.post("https://api.anthropic.com/v1/messages").mock(side_effect=_recorder(seen))

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


def _recorder(seen: list[str]):
    payloads = [
        {"hook": "一条指令不够,作者给出一套可复用的流程。"},
        {
            "background": "作者想回答 AI 写代码到底怎么做才稳。",
            "core_argument": "流程分为环境搭建、产品设计、技术设计、实现和人工验证五步。",
            "conclusion": "Git、AI 自测、人工验证这三件事不能省。",
        },
        {"score": 81, "rationale": "给出了具体的工具与步骤,不是空泛的方法论。"},
        {
            "chapters": [
                {
                    "title": "开场:为什么一条指令不够",
                    "key_points": ["作者指出直接发指令产出的结果常常和预期不一致。"],
                    "summary": "作者先说明为什么一条指令不够。",
                    "key_moments": [
                        {"quote": ANCHORS[0], "takeaway": "主流选项是 Codex 和 Cloud Code。"}
                    ],
                },
                {
                    "title": "环境搭建",
                    "key_points": ["初始化 Git 仓库,并用 AGENTS.md 固定规则。"],
                    "key_moments": [
                        {"quote": ANCHORS[1], "takeaway": "规则写进 AGENTS.md,只做一次。"}
                    ],
                },
                {
                    "title": "人工验证",
                    "key_points": ["AI 自测覆盖不到交互体验,最后必须人工过一遍。"],
                    "key_moments": [
                        {"quote": ANCHORS[2], "takeaway": "自测覆盖不了交互与边界情况。"}
                    ],
                },
            ]
        },
        {"entities": [{"name": "Codex", "kind": "product", "count": 3}]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(
            "\n".join(
                part.get("text", "")
                for message in body.get("messages", [])
                for part in _parts(message)
            )
        )
        payload = payloads[min(len(seen) - 1, len(payloads) - 1)]
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(payload)}]})

    return handler


def _parts(message: dict) -> list[dict]:
    content = message.get("content")
    if isinstance(content, str):
        return [{"text": content}]
    return [part for part in content or [] if isinstance(part, dict)]


def _transcript() -> dict:
    segments = []
    for index, line in enumerate(LINES):
        start = index * 200.0
        segments.append(
            {
                "id": index,
                "seek": 0,
                "start": start,
                "end": start + 200.0,
                "text": line,
                "tokens": [],
                "temperature": 0.0,
                "avg_logprob": 0.0,
                "compression_ratio": 1.0,
                "no_speech_prob": 0.0,
            }
        )
    return {
        "text": "".join(LINES),
        "duration": 600.0,
        "language": "chinese",
        "segments": segments,
    }


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


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["state"] in {"done", "partial", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("job did not finish")
