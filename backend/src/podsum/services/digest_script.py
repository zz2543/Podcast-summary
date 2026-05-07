from __future__ import annotations

from typing import Any


def build(episode_detail: Any, lang: str) -> str:
    labels = _labels(lang)
    lines: list[str] = []

    hook = _value(episode_detail, "hook")
    if hook:
        lines.append(f"{labels['hook']}: {hook}")

    three_act = _value(episode_detail, "three_act")
    if isinstance(three_act, dict):
        for key in ("background", "core_argument", "conclusion"):
            value = str(three_act.get(key, "")).strip()
            if value:
                lines.append(f"{labels[key]}: {value}")

    for index, chapter in enumerate(_list_value(episode_detail, "chapters"), start=1):
        title = str(_value(chapter, "title") or "").strip()
        key_points = [str(item).strip() for item in _list_value(chapter, "key_points") if str(item).strip()]
        if not title and not key_points:
            continue
        points = "; ".join(key_points)
        if points:
            lines.append(f"{labels['chapter']} {index}: {title} - {points}")
        else:
            lines.append(f"{labels['chapter']} {index}: {title}")

    return "\n".join(lines).strip()


def _labels(lang: str) -> dict[str, str]:
    if lang == "zh":
        return {
            "hook": "一句话摘要",
            "background": "背景",
            "core_argument": "核心论点",
            "conclusion": "结论",
            "chapter": "章节",
        }
    return {
        "hook": "Hook",
        "background": "Background",
        "core_argument": "Core argument",
        "conclusion": "Conclusion",
        "chapter": "Chapter",
    }


def _value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _list_value(source: Any, key: str) -> list[Any]:
    value = _value(source, key)
    return value if isinstance(value, list) else []
