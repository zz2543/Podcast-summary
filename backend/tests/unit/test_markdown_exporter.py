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
        }
    )

    assert markdown.startswith("# Episode title\n")
    assert "## Metadata" in markdown
    assert "- Duration: 2:05" in markdown
    assert "## Hook\nA useful reason to listen" in markdown
    assert "### Core Argument\nArgument." in markdown
