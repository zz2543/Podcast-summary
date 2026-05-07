from __future__ import annotations

from types import SimpleNamespace

from podsum.exporters.markdown import render


def test_markdown_render_emits_us1_sections() -> None:
    markdown = render(
        {
            "episode": SimpleNamespace(
                title="Episode title",
                podcast_name="Pod",
                source_type="youtube",
                source_ref="https://example.test/watch",
                duration_seconds=125,
                language="en",
            ),
            "artifact": SimpleNamespace(
                hook="A useful reason to listen",
                three_act={
                    "background": "Context.",
                    "core_argument": "Argument.",
                    "conclusion": "Ending.",
                },
            ),
            "chapters": [
                SimpleNamespace(
                    idx=0,
                    title="Opening",
                    start_ms=0,
                    end_ms=65_000,
                    key_points=["Point one"],
                    quotes=[
                        SimpleNamespace(text="Verbatim quote.", start_ms=12_000, verified=True)
                    ],
                )
            ],
            "entities": [
                SimpleNamespace(name="Ada Lovelace", kind="person", count=2),
                SimpleNamespace(name="DeepSeek", kind="product", count=1),
            ],
        }
    )

    assert markdown.startswith("# Episode title\n")
    assert "## Metadata" in markdown
    assert "- Duration: 2:05" in markdown
    assert "## Hook\nA useful reason to listen" in markdown
    assert "### Core Argument\nArgument." in markdown
    assert "## Chapters" in markdown
    assert "[00:12](#t=12000) \"Verbatim quote.\"" in markdown
    assert "### Person\n- Ada Lovelace × 2" in markdown
