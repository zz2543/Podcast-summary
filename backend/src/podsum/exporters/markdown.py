from __future__ import annotations

from typing import Any


def render(episode_detail: Any) -> str:
    episode = _value(episode_detail, "episode")
    artifact = _value(episode_detail, "artifact")
    title = _value(episode, "title") or "Untitled episode"

    lines = [
        f"# {title}",
        "",
        "## Metadata",
        f"- Podcast: {_value(episode, 'podcast_name') or 'Unknown'}",
        f"- Source type: {_value(episode, 'source_type') or 'Unknown'}",
        f"- Source: {_value(episode, 'source_ref') or 'Unknown'}",
        f"- Duration: {_duration_label(_value(episode, 'duration_seconds'))}",
        f"- Language: {_value(episode, 'language') or 'Unknown'}",
    ]

    hook = _value(artifact, "hook")
    if hook:
        lines.extend(["", "## Hook", str(hook)])

    three_act = _value(artifact, "three_act")
    if isinstance(three_act, dict):
        lines.extend(
            [
                "",
                "## Three-Act Summary",
                "",
                "### Background",
                str(three_act.get("background", "")).strip(),
                "",
                "### Core Argument",
                str(three_act.get("core_argument", "")).strip(),
                "",
                "### Conclusion",
                str(three_act.get("conclusion", "")).strip(),
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _duration_label(value: Any) -> str:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return "Unknown"
    minutes, remaining = divmod(seconds, 60)
    return f"{minutes}:{remaining:02d}"
