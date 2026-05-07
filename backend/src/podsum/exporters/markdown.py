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

    chapters = _list_value(episode_detail, "chapters")
    if chapters:
        lines.extend(["", "## Chapters"])
        for chapter in chapters:
            lines.extend(
                [
                    "",
                    f"### {_value(chapter, 'idx') + 1}. {_value(chapter, 'title')}",
                    f"- Time: {_timestamp(_value(chapter, 'start_ms'))}–{_timestamp(_value(chapter, 'end_ms'))}",
                    "- Key points:",
                ]
            )
            for point in _list_value(chapter, "key_points"):
                lines.append(f"  - {point}")
            quotes = [
                quote
                for quote in _list_value(chapter, "quotes")
                if _value(quote, "verified") is not False
            ]
            if quotes:
                lines.append("- Quotes:")
                for quote in quotes:
                    start_ms = _value(quote, "start_ms")
                    lines.append(
                        f"  - [{_timestamp(start_ms)}](#t={start_ms}) \"{_value(quote, 'text')}\""
                    )

    entities = _list_value(episode_detail, "entities")
    if entities:
        lines.extend(["", "## Entities"])
        for kind in ("person", "book", "product"):
            grouped = [entity for entity in entities if _value(entity, "kind") == kind]
            if not grouped:
                continue
            lines.extend(["", f"### {kind.title()}"])
            for entity in grouped:
                lines.append(f"- {_value(entity, 'name')} × {_value(entity, 'count')}")

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


def _list_value(source: Any, key: str) -> list[Any]:
    value = _value(source, key)
    return value if isinstance(value, list) else []


def _timestamp(value: Any) -> str:
    try:
        total_seconds = max(0, int(value) // 1000)
    except (TypeError, ValueError):
        total_seconds = 0
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"
