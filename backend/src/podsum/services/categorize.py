"""On-demand AI categorisation runs (feature 004).

A run starts only from POST /api/categorize: nothing in the pipeline calls
this. It reads one snapshot of the videos that are in no category yet (and
that the user has not taken out of one by hand), asks the model which new
categories they need on top of the existing ones (phase A), then files each
of them into one category in batches (phase B), and ends with a proposal.
Videos already in a category are never reconsidered. A run never writes to
the database: the user's edited choices come back through
POST /api/categories/apply, which re-checks every row.

Runs live in memory. At most one is running; the last finished one is kept so
the client can collect its result.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.domain.categorizer import (
    AssignPayload,
    CategoryOption,
    EpisodeDigest,
    ProposalInput,
    TaxonomyPayload,
    assign_batch,
    batches,
    build_proposal,
    existing_key,
    library_language,
    name_key,
    parse_assignments,
    parse_taxonomy,
    taxonomy_limits,
    taxonomy_slots,
)
from podsum.domain.prompt_assembler import PromptAssembler
from podsum.persistence.models import Chapter, Entity, Episode, SummaryArtifact, new_ulid, utc_now
from podsum.persistence.repo import CategoryRepo
from podsum.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

RunState = Literal["running", "ready", "failed", "cancelled"]

SUMMARIZED_STATUSES = ("done", "partial")


class RunInProgress(RuntimeError):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__("an AI categorisation run is already in progress")


class NothingToCategorize(RuntimeError):
    """No episode may take part: all are filed, locked, unsummarised, or there are none."""


@dataclass
class Snapshot:
    digests: list[EpisodeDigest]
    existing: list[CategoryOption]
    skipped_categorized: int = 0
    skipped_locked: int = 0
    skipped_no_summary: int = 0


@dataclass
class CategorizeRun:
    run_id: str
    total: int
    state: RunState = "running"
    phase: Literal["taxonomy", "assign"] = "taxonomy"
    done: int = 0
    proposal: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)

    def payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state,
            "phase": self.phase,
            "progress": {"done": self.done, "total": self.total},
            "error": self.error,
            "proposal": self.proposal,
        }

    def finish(self, state: RunState, *, error: str | None = None) -> None:
        # A cancelled run stays cancelled even if its last model call returns.
        if self.state != "running":
            return
        self.state = state
        self.error = error
        self.finished_at = utc_now()


def take_snapshot(session: Session) -> Snapshot:
    """Everything a run needs, read once. Starts from `episode`, so orphaned
    `summary_artifact` rows are never considered."""
    episodes = list(session.scalars(select(Episode).order_by(Episode.created_at)))
    ids = [episode.id for episode in episodes]
    hooks = {
        episode_id: hook
        for episode_id, hook in session.execute(
            select(SummaryArtifact.episode_id, SummaryArtifact.hook).where(
                SummaryArtifact.episode_id.in_(ids)
            )
        )
    }
    chapters: dict[str, list[str]] = defaultdict(list)
    for episode_id, title in session.execute(
        select(Chapter.episode_id, Chapter.title)
        .where(Chapter.episode_id.in_(ids))
        .order_by(Chapter.episode_id, Chapter.idx)
    ):
        chapters[episode_id].append(title)
    entities: dict[str, list[str]] = defaultdict(list)
    for episode_id, name in session.execute(
        select(Entity.episode_id, Entity.name)
        .where(Entity.episode_id.in_(ids))
        .order_by(Entity.episode_id, Entity.count.desc(), Entity.id)
    ):
        entities[episode_id].append(name)

    snapshot = Snapshot(
        digests=[],
        existing=[
            CategoryOption(key=existing_key(category.id), name=category.name)
            for category in CategoryRepo(session).list_ordered()
        ],
    )
    for episode in episodes:
        # A video already in a category stays there, whoever put it there:
        # a run only files what is still Uncategorized, into an existing
        # category or a new one.
        if episode.category_id is not None:
            snapshot.skipped_categorized += 1
            continue
        # Taken out of a category by hand: the user said "not there", so AI
        # leaves it alone until they hand it back ("Let AI Categorize").
        if episode.category_origin == "manual":
            snapshot.skipped_locked += 1
            continue
        hook = (hooks.get(episode.id) or "").strip()
        if episode.status not in SUMMARIZED_STATUSES or not hook:
            snapshot.skipped_no_summary += 1
            continue
        snapshot.digests.append(
            EpisodeDigest(
                id=episode.id,
                title=episode.title,
                hook=hook,
                chapter_titles=tuple(chapters[episode.id]),
                entities=tuple(entities[episode.id]),
            )
        )
    return snapshot


class CategorizeRunner:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings: Settings,
        llm_provider: Callable[[], LLMClient],
        prompt_assembler: PromptAssembler | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.llm_provider = llm_provider
        self.prompts = prompt_assembler or PromptAssembler()
        self._run: CategorizeRun | None = None

    def start(self) -> CategorizeRun:
        if self._run is not None and self._run.state == "running":
            raise RunInProgress(self._run.run_id)
        with self.session_factory() as session:
            snapshot = take_snapshot(session)
        if not snapshot.digests:
            if snapshot.skipped_no_summary:
                raise NothingToCategorize("no uncategorized video has a summary yet")
            if snapshot.skipped_categorized or snapshot.skipped_locked:
                raise NothingToCategorize("every video is already in a category or was taken out by hand")
            raise NothingToCategorize("the library is empty")
        batch_count = -(-len(snapshot.digests) // self.settings.CATEGORIZE_BATCH_SIZE)
        run = CategorizeRun(run_id=new_ulid(), total=1 + batch_count)
        run.task = asyncio.create_task(self._execute(run, snapshot))
        self._run = run
        return run

    def get(self, run_id: str) -> CategorizeRun | None:
        if self._run is not None and self._run.run_id == run_id:
            return self._run
        return None

    def cancel(self, run_id: str) -> CategorizeRun | None:
        run = self.get(run_id)
        if run is not None:
            # The model call in flight runs to completion in its thread; its
            # result is discarded because the run is no longer running.
            run.finish("cancelled")
        return run

    async def shutdown(self) -> None:
        run = self._run
        if run is None or run.task is None or run.task.done():
            return
        run.finish("cancelled")
        run.task.cancel()
        try:
            await run.task
        except asyncio.CancelledError:
            pass

    async def _execute(self, run: CategorizeRun, snapshot: Snapshot) -> None:
        try:
            await self._run_phases(run, snapshot)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced to the user as the run's error
            logger.warning("AI categorisation run %s failed: %s", run.run_id, exc)
            run.finish("failed", error=_describe(exc))

    async def _run_phases(self, run: CategorizeRun, snapshot: Snapshot) -> None:
        llm = self.llm_provider()
        lang = library_language(snapshot.digests)

        min_new, max_new = taxonomy_limits(
            len(snapshot.existing),
            max_new=self.settings.CATEGORIZE_MAX_NEW,
            max_initial=self.settings.CATEGORIZE_MAX_INITIAL,
        )
        prompt = self.prompts.render(
            "category_taxonomy",
            "v1",
            **taxonomy_slots(
                [option.name for option in snapshot.existing],
                snapshot.digests,
                min_new=min_new,
                max_new=max_new,
                lang=lang,
            ),
        )
        payload = await asyncio.to_thread(llm.complete_json, prompt, TaxonomyPayload)
        if run.state != "running":
            return
        new_categories = parse_taxonomy(
            payload, {name_key(option.name) for option in snapshot.existing}, max_new
        )
        run.done = 1
        run.phase = "assign"

        options = [
            *snapshot.existing,
            *(CategoryOption(key=new.key, name=new.name) for new in new_categories),
        ]
        suggestions: dict[str, str | None] = {}
        failed = 0
        last_error: Exception | None = None
        groups = list(batches(snapshot.digests, self.settings.CATEGORIZE_BATCH_SIZE))
        for group in groups:
            batch = assign_batch(options, group, lang=lang)
            try:
                prompt = self.prompts.render("category_assign", "v1", **batch.slots)
                payload = await asyncio.to_thread(llm.complete_json, prompt, AssignPayload)
                suggestions.update(parse_assignments(payload, batch))
            except Exception as exc:  # noqa: BLE001 — one batch failing leaves the rest usable
                logger.warning("AI categorisation run %s: a batch failed: %s", run.run_id, exc)
                failed += 1
                last_error = exc
                suggestions.update({digest.id: None for digest in group})
            if run.state != "running":
                return
            run.done += 1

        if failed == len(groups):
            # A provider problem (no balance, bad key) is worth naming;
            # anything else is summed up.
            code = _provider_error(last_error) if last_error is not None else None
            run.finish("failed", error=code or "every assignment batch failed")
            return
        run.proposal = build_proposal(
            ProposalInput(
                digests=snapshot.digests,
                suggestions=suggestions,
                existing=snapshot.existing,
                new_categories=new_categories,
                skipped_categorized=snapshot.skipped_categorized,
                skipped_locked=snapshot.skipped_locked,
                skipped_no_summary=snapshot.skipped_no_summary,
                failed_batches=failed,
            )
        )
        run.finish("ready")


# Provider refusals the user can act on. The client turns these codes into a
# sentence; anything else is passed through as the provider's own message.
_PROVIDER_ERRORS = {
    401: "llm_auth_failed",
    403: "llm_auth_failed",
    402: "llm_insufficient_balance",
    429: "llm_rate_limited",
}


def _provider_error(exc: Exception) -> str | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    text = str(exc).lower()
    # OpenAI-style APIs report an empty account as 429 "insufficient_quota".
    if "insufficient balance" in text or "insufficient_quota" in text:
        return "llm_insufficient_balance"
    return _PROVIDER_ERRORS.get(status) if isinstance(status, int) else None


def _describe(exc: Exception) -> str:
    code = _provider_error(exc)
    if code is not None:
        return code
    text = str(exc).strip() or type(exc).__name__
    return text if len(text) <= 300 else text[:299] + "…"
