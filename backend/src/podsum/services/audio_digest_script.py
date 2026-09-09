from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from podsum.domain.prompt_assembler import PromptAssembler
from podsum.services.llm_client import LLMClient


class AudioDigestScript(BaseModel):
    script: str


PROMPT_VERSION = "v1"


def generate_or_load(
    episode_dir: Path, transcript: str, lang: str, llm_client: LLMClient, assembler: PromptAssembler
) -> tuple[str, bool]:
    if not transcript.strip():
        raise ValueError("cannot generate an audio digest without a transcript")
    fingerprint = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
    cache_path = episode_dir / "digest_script.json"
    if cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if payload.get("fingerprint") == fingerprint and payload.get("prompt_version") == PROMPT_VERSION:
                script = str(payload.get("script", "")).strip()
                if script:
                    return script, True
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    prompt = assembler.render("audio_digest", PROMPT_VERSION, lang=_language_instruction(lang), transcript=transcript)
    payload = llm_client.complete_json(prompt, AudioDigestScript)
    script = AudioDigestScript.model_validate(payload).script.strip()
    if not script:
        raise ValueError("LLM returned an empty audio digest script")
    cache_path.write_text(json.dumps({"fingerprint": fingerprint, "prompt_version": PROMPT_VERSION, "script": script}, ensure_ascii=False, indent=2), encoding="utf-8")
    return script, False


def _language_instruction(lang: str) -> str:
    if lang == "zh":
        return "Simplified Chinese (the same language as the video)"
    if lang == "en":
        return "English (the same language as the video)"
    return "the original language mix in the video; preserve each Chinese and English passage in its original language"
