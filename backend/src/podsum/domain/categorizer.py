"""Video categories (feature 004): names, AI-categorisation prompts and parsing.

Everything here is pure. `services/categorize.py` orchestrates a run and the
API layer writes to the database; this module decides what a name means, what
the model is shown, what of its answer is kept, and what a proposal contains.

The model never sees a ULID. Episodes and categories are labelled `e1`, `c1`…
within one prompt and mapped back here, so a mistyped 26-character id cannot
put a video in the wrong place.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

MAX_NAME_LENGTH = 30

# The sidebar's fixed rows, in both UI languages. A category may not shadow one.
RESERVED_KEYS = frozenset({"全部", "未分类", "all", "uncategorized"})

NameErrorReason = Literal["empty", "too_long", "reserved"]

_NAME_MESSAGES: dict[str, str] = {
    "empty": "category name is empty",
    "too_long": f"category name is longer than {MAX_NAME_LENGTH} characters",
    "reserved": "category name is reserved",
}

SHORT_TITLE_CHARS = 80
SHORT_HOOK_CHARS = 120
LONG_HOOK_CHARS = 200
CHAPTER_TITLE_CHARS = 40
MAX_CHAPTERS = 8
MAX_ENTITIES = 5

UNTITLED = "(untitled)"

LIBRARY_LANGUAGES = {
    "zh": "Simplified Chinese",
    "en": "English",
}

# Mirrors domain.language: one CJK character carries roughly a Latin word.
_CJK = re.compile("[\\u3400-\\u4dbf\\u4e00-\\u9fff\\uf900-\\ufaff]")
_LATIN_WORD = re.compile(r"[A-Za-z]+")


class CategoryNameError(ValueError):
    def __init__(self, reason: NameErrorReason) -> None:
        self.reason = reason
        super().__init__(_NAME_MESSAGES[reason])


class TaxonomyError(RuntimeError):
    """The model proposed no usable category for a library that has none."""


# --------------------------------------------------------------------------- names


def normalize_display(name: str) -> str:
    return name.strip()


def name_key(name: str) -> str:
    """What "the same name" means: NFKC-folded, trimmed, case-insensitive."""
    return unicodedata.normalize("NFKC", name).strip().casefold()


def validate_name(name: str) -> str:
    """Return the display form of a category name, or raise CategoryNameError."""
    display = normalize_display(name)
    key = name_key(display)
    if not key:
        raise CategoryNameError("empty")
    if len(display) > MAX_NAME_LENGTH:
        raise CategoryNameError("too_long")
    if key in RESERVED_KEYS:
        raise CategoryNameError("reserved")
    return display


# ------------------------------------------------------------------------- digests


@dataclass(frozen=True)
class EpisodeDigest:
    """What the model may know about one episode, read once when a run starts."""

    id: str
    title: str | None
    hook: str
    chapter_titles: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()


def clip(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def short_line(digest: EpisodeDigest, label: str) -> str:
    title = clip(digest.title or UNTITLED, SHORT_TITLE_CHARS)
    return f"{label} {title} — {clip(digest.hook, SHORT_HOOK_CHARS)}"


def long_block(digest: EpisodeDigest, label: str) -> str:
    lines = [
        f"{label} {clip(digest.title or UNTITLED, SHORT_TITLE_CHARS)}",
        f"  summary: {clip(digest.hook, LONG_HOOK_CHARS)}",
    ]
    chapters = [clip(title, CHAPTER_TITLE_CHARS) for title in digest.chapter_titles[:MAX_CHAPTERS]]
    if chapters:
        lines.append("  chapters: " + "; ".join(chapters))
    entities = [name for name in digest.entities[:MAX_ENTITIES] if name.strip()]
    if entities:
        lines.append("  mentions: " + ", ".join(entities))
    return "\n".join(lines)


T = TypeVar("T")


def batches(items: Sequence[T], size: int) -> Iterator[list[T]]:
    if size < 1:
        raise ValueError("batch size must be positive")
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def library_language(digests: Iterable[EpisodeDigest]) -> str:
    """The `{lang}` slot: the language most of the library is written in."""
    cjk = 0
    latin_words = 0
    for digest in digests:
        text = f"{digest.title or ''} {digest.hook}"
        cjk += len(_CJK.findall(text))
        latin_words += len(_LATIN_WORD.findall(text))
    return LIBRARY_LANGUAGES["zh" if cjk >= latin_words else "en"]


# ----------------------------------------------------------------- phase A: taxonomy


class ProposedCategoryItem(BaseModel):
    name: str
    reason: str = ""


class TaxonomyPayload(BaseModel):
    new_categories: list[ProposedCategoryItem] = []


@dataclass(frozen=True)
class NewCategory:
    key: str  # "n:1", "n:2"… — stable within one run
    name: str
    reason: str = ""


def taxonomy_limits(existing_count: int, *, max_new: int, max_initial: int) -> tuple[int, int]:
    """(min_new, max_new) for phase A: an empty library must get a real taxonomy."""
    if existing_count == 0:
        return 3, max_initial
    return 0, max_new


def taxonomy_slots(
    existing_names: Sequence[str],
    digests: Sequence[EpisodeDigest],
    *,
    min_new: int,
    max_new: int,
    lang: str,
) -> dict[str, str]:
    existing = "\n".join(f"- {name}" for name in existing_names) or "(none)"
    episodes = "\n".join(short_line(digest, f"e{index}") for index, digest in enumerate(digests, 1))
    return {
        "existing": existing,
        "episodes": episodes,
        "min_new": str(min_new),
        "max_new": str(max_new),
        "lang": lang,
    }


def parse_taxonomy(
    payload: dict[str, Any], existing_keys: Iterable[str], max_new: int
) -> list[NewCategory]:
    """Keep the valid, distinct new names, at most `max_new` of them.

    A library without categories that ends up with none raises TaxonomyError:
    there would be nothing to put any video into.
    """
    parsed = TaxonomyPayload.model_validate(payload)
    existing = set(existing_keys)
    seen = set(existing)
    kept: list[NewCategory] = []
    for item in parsed.new_categories:
        if len(kept) >= max_new:
            break
        try:
            name = validate_name(item.name)
        except CategoryNameError:
            continue
        key = name_key(name)
        if key in seen:
            continue
        seen.add(key)
        kept.append(NewCategory(key=f"n:{len(kept) + 1}", name=name, reason=item.reason.strip()))
    if not existing and not kept:
        raise TaxonomyError("no_taxonomy")
    return kept


# ------------------------------------------------------------------- phase B: assign


class AssignmentItem(BaseModel):
    episode: str | int
    category: str | int | None = None


class AssignPayload(BaseModel):
    assignments: list[AssignmentItem] = []


@dataclass(frozen=True)
class CategoryOption:
    key: str  # "c:<category id>" for an existing category, "n:<k>" for a new one
    name: str


@dataclass(frozen=True)
class AssignBatch:
    slots: dict[str, str]
    episode_labels: dict[str, str]  # "e1" -> episode id
    category_labels: dict[str, str]  # "c1" -> option key, plus name_key(name) -> option key


def assign_batch(
    options: Sequence[CategoryOption], digests: Sequence[EpisodeDigest], *, lang: str
) -> AssignBatch:
    category_labels: dict[str, str] = {}
    category_lines = []
    for index, option in enumerate(options, 1):
        label = f"c{index}"
        category_labels[label] = option.key
        # Models sometimes answer with the name instead of the label.
        category_labels.setdefault(name_key(option.name), option.key)
        category_lines.append(f"{label} {option.name}")
    episode_labels = {f"e{index}": digest.id for index, digest in enumerate(digests, 1)}
    blocks = [long_block(digest, f"e{index}") for index, digest in enumerate(digests, 1)]
    return AssignBatch(
        slots={
            "categories": "\n".join(category_lines),
            "episodes": "\n\n".join(blocks),
            "lang": lang,
        },
        episode_labels=episode_labels,
        category_labels=category_labels,
    )


def parse_assignments(payload: dict[str, Any], batch: AssignBatch) -> dict[str, str | None]:
    """Episode id -> option key, or None when there is no usable suggestion.

    Unknown episode labels are dropped; an unknown category counts as "none
    fits"; an episode given two different answers gets neither; an episode the
    model skipped gets None.
    """
    parsed = AssignPayload.model_validate(payload)
    answers: dict[str, set[str | None]] = {}
    for item in parsed.assignments:
        label = str(item.episode).strip().lower()
        episode_id = batch.episode_labels.get(label)
        if episode_id is None:
            continue
        answers.setdefault(episode_id, set()).add(_option_key(item.category, batch))
    result: dict[str, str | None] = {}
    for episode_id in batch.episode_labels.values():
        votes = answers.get(episode_id, set())
        result[episode_id] = next(iter(votes)) if len(votes) == 1 else None
    return result


def _option_key(raw: str | int | None, batch: AssignBatch) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return batch.category_labels.get(text.lower()) or batch.category_labels.get(name_key(text))


# ------------------------------------------------------------------------ proposal


@dataclass
class ProposalInput:
    """Everything a proposal is built from. Only uncategorized episodes take
    part in a run, so every suggestion files a video that is in no category."""

    digests: Sequence[EpisodeDigest]
    suggestions: dict[str, str | None]
    existing: Sequence[CategoryOption]  # in sidebar order
    new_categories: Sequence[NewCategory]
    skipped_categorized: int = 0
    skipped_locked: int = 0
    skipped_no_summary: int = 0
    failed_batches: int = 0


def existing_key(category_id: str) -> str:
    return f"c:{category_id}"


def build_proposal(data: ProposalInput) -> dict[str, Any]:
    """The `proposal` object of GET /api/categorize/{run_id} (contracts/http-api.md)."""
    changes: list[dict[str, Any]] = []
    no_suggestion = 0
    used: set[str] = set()
    for digest in data.digests:
        target = data.suggestions.get(digest.id)
        if target is None:
            no_suggestion += 1
            continue
        used.add(target)
        changes.append({"episode_id": digest.id, "title": digest.title, "to_key": target})

    categories: list[dict[str, Any]] = []
    for option in data.existing:
        if option.key in used:
            categories.append(
                {
                    "key": option.key,
                    "category_id": option.key.removeprefix("c:"),
                    "name": option.name,
                    "is_new": False,
                }
            )
    for new in data.new_categories:
        if new.key in used:
            categories.append(
                {
                    "key": new.key,
                    "category_id": None,
                    "name": new.name,
                    "is_new": True,
                    "reason": new.reason,
                }
            )

    return {
        "categories": categories,
        "changes": changes,
        "skipped": {
            "categorized": data.skipped_categorized,
            "locked": data.skipped_locked,
            "no_summary": data.skipped_no_summary,
            "no_suggestion": no_suggestion,
        },
        "failed_batches": data.failed_batches,
    }


# --------------------------------------------------------------------------- apply

SkipReason = Literal["episode_gone", "locked", "changed", "category_gone"]


def apply_decision(
    *,
    episode_exists: bool,
    current_category_id: str | None,
    current_origin: str | None,
    from_category_id: str | None,
    target_exists: bool,
) -> SkipReason | None:
    """Why one accepted suggestion must not be written, or None to write it.

    This is the server-side guarantee behind SC-002: whatever the client sends,
    a video the user placed by hand, or moved since the proposal was made, is
    left alone.
    """
    if not episode_exists:
        return "episode_gone"
    if current_origin == "manual":
        return "locked"
    if current_category_id != from_category_id:
        return "changed"
    if not target_exists:
        return "category_gone"
    return None
