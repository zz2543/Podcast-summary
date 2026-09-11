from __future__ import annotations

from podsum.domain.language import (
    LANGUAGE_INSTRUCTIONS,
    character_counts,
    classify,
    dominant,
    instruction,
)


def seg(text: str) -> dict[str, str]:
    return {"text": text}


CHINESE_WITH_TERMS = [
    seg("今天我们来讲讲如何使用 AI 写代码,你可以装个 Codex 或者 Cloud Code。"),
    seg("最后他总结说可以用 Electron 加 React 再加上 TypeScript。"),
]


def test_character_counts_separates_scripts() -> None:
    cjk, latin = character_counts([seg("你好 hello")])
    assert (cjk, latin) == (2, 5)


def test_chinese_episode_with_english_terms_is_chinese() -> None:
    # The bug: ASR tags the term-heavy utterances `en`, the episode came out
    # "mixed", and the prompts then asked for a summary "in mixed".
    assert classify(CHINESE_WITH_TERMS) == "zh"
    assert dominant(CHINESE_WITH_TERMS) == "zh"


def test_genuinely_bilingual_episode_is_mixed() -> None:
    segments = [seg("这是一段完整的中文内容用来占据篇幅"), seg("and this is an equally long English passage here")]
    assert classify(segments) == "mixed"


def test_english_episode_is_english() -> None:
    assert classify([seg("a purely english transcript")]) == "en"
    assert dominant([seg("a purely english transcript")]) == "en"


def test_empty_transcript_has_no_language() -> None:
    assert classify([]) is None
    assert dominant([], fallback="zh") == "zh"


def test_instruction_never_leaks_a_non_language() -> None:
    assert instruction("zh") == LANGUAGE_INSTRUCTIONS["zh"]
    assert instruction("en") == LANGUAGE_INSTRUCTIONS["en"]
    # "mixed" is a description of the source, not something a model can write in.
    assert instruction("mixed", CHINESE_WITH_TERMS) == LANGUAGE_INSTRUCTIONS["zh"]
    assert instruction(None, CHINESE_WITH_TERMS) == LANGUAGE_INSTRUCTIONS["zh"]
    assert "mixed" not in instruction("mixed", CHINESE_WITH_TERMS)


def test_dominant_falls_back_when_nothing_readable() -> None:
    assert dominant([seg("123 !!! ???")]) == "en"
