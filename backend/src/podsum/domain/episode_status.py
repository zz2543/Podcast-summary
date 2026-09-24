"""Episode status is a fact about what the episode *has*, not about the last job.

It used to be copied from whichever job touched the episode last, which made
the list lie in both directions:

* a finished episode turned "failed" because a later re-run died in fetch,
  although every section from the first run was still on disk;
* an on-demand audio digest that ran out of TTS balance turned a complete
  summary into "partial".

So the status is derived from the artifact's per-section ``stage_status`` and
whether a summary job is still running. Job outcomes stay on the job, where the
detail page can still say "the last re-run failed" without repainting the list.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: Sections without which there is no summary to read.
CORE_SECTIONS = ("hook", "three_act", "chapters")
#: Sections the reader can do without; failing one leaves the episode readable.
OPTIONAL_SECTIONS = ("usefulness", "entities")
# ``tts`` is deliberately in neither: the audio digest is an add-on the reader
# asks for later, and its outcome is shown on its own control.


def derive(
    stage_status: Mapping[str, Any] | None,
    *,
    summary_job_active: bool,
    summary_job_ran: bool,
) -> str:
    """Return one of ``pending | processing | done | partial | failed``.

    ``processing``  a summary job is queued or running.
    ``done``        every core section is present, no optional one failed.
    ``partial``     the summary is readable, but an optional section failed.
    ``failed``      a summary job ran to the end and the summary is incomplete.
    ``pending``     nothing has run yet.
    """
    if summary_job_active:
        return "processing"
    stage_status = stage_status or {}
    if all(stage_status.get(section) == "present" for section in CORE_SECTIONS):
        if any(stage_status.get(section) == "failed_after_retries" for section in OPTIONAL_SECTIONS):
            return "partial"
        return "done"
    return "failed" if summary_job_ran else "pending"
