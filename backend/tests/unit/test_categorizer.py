from __future__ import annotations

import pytest
from pydantic import ValidationError

from podsum.domain.categorizer import (
    MAX_NAME_LENGTH,
    CategoryNameError,
    CategoryOption,
    EpisodeDigest,
    NewCategory,
    ProposalInput,
    TaxonomyError,
    apply_decision,
    assign_batch,
    batches,
    build_proposal,
    clip,
    library_language,
    long_block,
    name_key,
    parse_assignments,
    parse_taxonomy,
    short_line,
    taxonomy_limits,
    taxonomy_slots,
    validate_name,
)

# ---------------------------------------------------------------------- names


def test_name_key_folds_width_case_and_surrounding_space() -> None:
    assert name_key("  ＡＩ　编程 ") == name_key("ai 编程")
    assert name_key("Investing") == name_key("INVESTING")


def test_validate_name_trims_but_keeps_the_written_form() -> None:
    assert validate_name("  ＡＩ 编程\t") == "ＡＩ 编程"


@pytest.mark.parametrize("raw", ["", "   ", "　　"])
def test_validate_name_rejects_empty(raw: str) -> None:
    with pytest.raises(CategoryNameError) as error:
        validate_name(raw)
    assert error.value.reason == "empty"


def test_validate_name_length_limit_counts_characters() -> None:
    assert validate_name("字" * MAX_NAME_LENGTH) == "字" * MAX_NAME_LENGTH
    with pytest.raises(CategoryNameError) as error:
        validate_name("字" * (MAX_NAME_LENGTH + 1))
    assert error.value.reason == "too_long"


@pytest.mark.parametrize("raw", ["全部", "未分类", "All", " UNCATEGORIZED ", "ａｌｌ"])
def test_validate_name_rejects_the_sidebar_fixed_rows(raw: str) -> None:
    with pytest.raises(CategoryNameError) as error:
        validate_name(raw)
    assert error.value.reason == "reserved"


# -------------------------------------------------------------------- digests


def _digest(n: int, **overrides: object) -> EpisodeDigest:
    values: dict[str, object] = {
        "id": f"EP{n:02d}",
        "title": f"标题 {n}",
        "hook": f"一句话总结 {n}",
    }
    values.update(overrides)
    return EpisodeDigest(**values)  # type: ignore[arg-type]


def test_clip_collapses_whitespace_and_marks_the_cut() -> None:
    assert clip("a  b\n c", 10) == "a b c"
    assert clip("x" * 12, 10) == "x" * 9 + "…"
    assert len(clip("x" * 500, 120)) == 120


def test_short_line_uses_label_title_and_clipped_hook() -> None:
    line = short_line(_digest(1, hook="很" * 300), "e1")
    assert line.startswith("e1 标题 1 — ")
    assert line.endswith("…")
    assert "EP01" not in line


def test_short_line_names_untitled_episodes() -> None:
    assert short_line(_digest(1, title=None), "e3").startswith("e3 (untitled)")


def test_long_block_includes_chapters_and_entities_within_limits() -> None:
    digest = _digest(
        1,
        chapter_titles=tuple(f"章节{i}" for i in range(12)),
        entities=("Claude", " ", "Codex", "a", "b", "c", "d"),
    )
    block = long_block(digest, "e1")
    assert "章节7" in block and "章节8" not in block
    assert "mentions: Claude, Codex, a, b" in block


def test_long_block_omits_empty_sections() -> None:
    block = long_block(_digest(1), "e1")
    assert "chapters" not in block and "mentions" not in block


def test_batches_split_evenly_and_reject_nonsense_sizes() -> None:
    assert list(batches([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert list(batches([], 3)) == []
    with pytest.raises(ValueError):
        list(batches([1], 0))


def test_library_language_follows_the_majority_of_text() -> None:
    assert library_language([_digest(1, title="Claude Code 入门", hook="讲怎么装好并开始用")]) == (
        "Simplified Chinese"
    )
    assert library_language([_digest(1, title="Intro to Claude Code", hook="How to set it up")]) == "English"


# ------------------------------------------------------------------- taxonomy


def test_taxonomy_limits_force_a_real_taxonomy_for_an_empty_library() -> None:
    assert taxonomy_limits(0, max_new=5, max_initial=10) == (3, 10)
    assert taxonomy_limits(2, max_new=5, max_initial=10) == (0, 5)


def test_taxonomy_slots_list_existing_names_and_label_episodes() -> None:
    slots = taxonomy_slots(["投资"], [_digest(1), _digest(2)], min_new=0, max_new=5, lang="English")
    assert slots["existing"] == "- 投资"
    assert slots["episodes"].splitlines()[1].startswith("e2 ")
    assert (slots["min_new"], slots["max_new"], slots["lang"]) == ("0", "5", "English")
    assert taxonomy_slots([], [], min_new=3, max_new=10, lang="x")["existing"] == "(none)"


def test_parse_taxonomy_drops_invalid_duplicate_and_existing_names() -> None:
    payload = {
        "new_categories": [
            {"name": "AI 编程", "reason": " 讲 agent "},
            {"name": "ai 编程"},
            {"name": "投资"},
            {"name": "  "},
            {"name": "全部"},
            {"name": "字" * 31},
            {"name": "历史"},
        ]
    }
    kept = parse_taxonomy(payload, {name_key("投资")}, max_new=5)
    assert kept == [
        NewCategory(key="n:1", name="AI 编程", reason="讲 agent"),
        NewCategory(key="n:2", name="历史", reason=""),
    ]


def test_parse_taxonomy_caps_the_number_of_new_categories() -> None:
    payload = {"new_categories": [{"name": f"类{i}"} for i in range(8)]}
    assert [c.key for c in parse_taxonomy(payload, set(), max_new=3)] == ["n:1", "n:2", "n:3"]


def test_parse_taxonomy_fails_when_an_empty_library_gets_nothing() -> None:
    with pytest.raises(TaxonomyError):
        parse_taxonomy({"new_categories": [{"name": "全部"}]}, set(), max_new=5)


def test_parse_taxonomy_allows_no_new_names_when_categories_exist() -> None:
    assert parse_taxonomy({"new_categories": []}, {"投资"}, max_new=5) == []


def test_parse_taxonomy_rejects_a_malformed_payload() -> None:
    with pytest.raises(ValidationError):
        parse_taxonomy({"new_categories": "AI"}, set(), max_new=5)


# --------------------------------------------------------------------- assign

OPTIONS = [CategoryOption(key="c:CAT1", name="投资"), CategoryOption(key="n:1", name="AI 编程")]


def test_assign_batch_labels_categories_and_episodes() -> None:
    batch = assign_batch(OPTIONS, [_digest(1), _digest(2)], lang="Simplified Chinese")
    assert batch.slots["categories"] == "c1 投资\nc2 AI 编程"
    assert batch.slots["episodes"].split("\n\n")[1].startswith("e2 ")
    assert batch.slots["lang"] == "Simplified Chinese"
    assert batch.episode_labels == {"e1": "EP01", "e2": "EP02"}
    assert batch.category_labels["c2"] == "n:1"
    assert batch.category_labels[name_key("AI 编程")] == "n:1"


def test_parse_assignments_applies_every_contract_rule() -> None:
    digests = [_digest(n) for n in range(1, 8)]
    batch = assign_batch(OPTIONS, digests, lang="x")
    payload = {
        "assignments": [
            {"episode": "e1", "category": "c1"},
            {"episode": " E2 ", "category": "C2"},  # case and spaces tolerated
            {"episode": "e3", "category": None},  # nothing fits
            {"episode": "e4", "category": "c9"},  # unknown category -> none
            {"episode": "e5", "category": "c1"},
            {"episode": "e5", "category": "c2"},  # contradictory -> dropped
            {"episode": "e6", "category": "c2"},
            {"episode": "e6", "category": "c2"},  # repeated but consistent
            {"episode": "e99", "category": "c1"},  # not in this batch
            {"episode": 7, "category": "ai 编程"},  # bare number; name instead of label
        ]
    }
    assert parse_assignments(payload, batch) == {
        "EP01": "c:CAT1",
        "EP02": "n:1",
        "EP03": None,
        "EP04": None,
        "EP05": None,
        "EP06": "n:1",
        "EP07": None,  # "7" is not the label "e7"
    }


def test_parse_assignments_marks_skipped_episodes_as_no_suggestion() -> None:
    batch = assign_batch(OPTIONS, [_digest(1), _digest(2)], lang="x")
    result = parse_assignments({"assignments": [{"episode": "e1", "category": "c1"}]}, batch)
    assert result == {"EP01": "c:CAT1", "EP02": None}


def test_parse_assignments_accepts_a_category_given_by_name() -> None:
    batch = assign_batch(OPTIONS, [_digest(1)], lang="x")
    assert parse_assignments({"assignments": [{"episode": "e1", "category": " 投资 "}]}, batch) == {
        "EP01": "c:CAT1"
    }


# ------------------------------------------------------------------- proposal


def test_build_proposal_lists_suggestions_and_counts_what_was_left_out() -> None:
    digests = [_digest(1), _digest(2), _digest(3)]
    proposal = build_proposal(
        ProposalInput(
            digests=digests,
            suggestions={"EP01": "n:1", "EP02": "c:CAT1", "EP03": None},
            existing=[
                CategoryOption("c:CAT1", "投资"),
                CategoryOption("c:CAT2", "历史"),
            ],
            new_categories=[NewCategory("n:1", "AI 编程", "讲 agent"), NewCategory("n:2", "没人用")],
            skipped_categorized=5,
            skipped_locked=2,
            skipped_no_summary=1,
            failed_batches=1,
        )
    )
    assert proposal["changes"] == [
        {"episode_id": "EP01", "title": "标题 1", "to_key": "n:1"},
        {"episode_id": "EP02", "title": "标题 2", "to_key": "c:CAT1"},
    ]
    assert proposal["skipped"] == {"categorized": 5, "locked": 2, "no_summary": 1, "no_suggestion": 1}
    assert proposal["failed_batches"] == 1
    # Only categories a change uses, existing ones first; unused ones are left out.
    assert proposal["categories"] == [
        {"key": "c:CAT1", "category_id": "CAT1", "name": "投资", "is_new": False},
        {"key": "n:1", "category_id": None, "name": "AI 编程", "is_new": True, "reason": "讲 agent"},
    ]


# ---------------------------------------------------------------------- apply


def _decide(**overrides: object) -> str | None:
    values: dict[str, object] = {
        "episode_exists": True,
        "current_category_id": None,
        "current_origin": None,
        "from_category_id": None,
        "target_exists": True,
    }
    values.update(overrides)
    return apply_decision(**values)  # type: ignore[arg-type]


def test_apply_decision_writes_when_nothing_changed() -> None:
    assert _decide() is None
    assert _decide(current_category_id="A", current_origin="auto", from_category_id="A") is None


def test_apply_decision_skip_reasons_in_priority_order() -> None:
    assert _decide(episode_exists=False, current_origin="manual") == "episode_gone"
    assert _decide(current_origin="manual", current_category_id="A", from_category_id="B") == "locked"
    assert _decide(current_category_id="A", current_origin="auto", from_category_id=None) == "changed"
    assert _decide(target_exists=False) == "category_gone"
