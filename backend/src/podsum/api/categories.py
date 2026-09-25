"""Categories and on-demand AI categorisation (feature 004).

Contract: specs/004-video-categories/contracts/http-api.md
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from podsum.api.episodes import SESSION_DEP, _api_error
from podsum.domain.categorizer import CategoryNameError, apply_decision, name_key, validate_name
from podsum.persistence.models import Category, Episode
from podsum.persistence.repo import CategoryRepo, DuplicateCategory
from podsum.services.categorize import CategorizeRunner, NothingToCategorize, RunInProgress

router = APIRouter(prefix="/api", tags=["categories"])


# ----------------------------------------------------------------- categories


@router.get("/categories")
async def list_categories(session: Session = SESSION_DEP) -> JSONResponse:
    return JSONResponse(content=_category_list(session))


@router.post("/categories")
async def create_category(body: dict[str, Any], session: Session = SESSION_DEP) -> JSONResponse:
    name = body.get("name")
    if not isinstance(name, str):
        return _api_error(400, "bad_input", "name must be a string")
    repo = CategoryRepo(session)
    try:
        category = repo.create(name)
    except CategoryNameError as error:
        return _name_error(error)
    except DuplicateCategory as error:
        return _duplicate(error)
    session.commit()
    return JSONResponse(status_code=201, content=_category_payload(category, 0))


# Registered before /categories/{category_id} so "order" is not taken for an id.
@router.put("/categories/order")
async def reorder_categories(body: dict[str, Any], session: Session = SESSION_DEP) -> JSONResponse:
    ids = body.get("ids")
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        return _api_error(400, "bad_input", "ids must be a list of category ids")
    try:
        CategoryRepo(session).reorder(ids)
    except ValueError as error:
        return _api_error(400, "bad_input", str(error))
    session.commit()
    return JSONResponse(content=_category_list(session))


@router.post("/categories/apply")
async def apply_categorization(body: dict[str, Any], session: Session = SESSION_DEP) -> JSONResponse:
    """Write the suggestions the user kept, in one transaction.

    Stateless on purpose: it works even if the run it came from is gone. Every
    row is re-checked, so a video placed by hand is never touched (SC-002).
    """
    new_categories = body.get("new_categories", [])
    assignments = body.get("assignments", [])
    if not isinstance(new_categories, list) or not isinstance(assignments, list):
        return _api_error(400, "bad_input", "new_categories and assignments must be lists")
    for item in assignments:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("episode_id"), str)
            and isinstance(item.get("to_key"), str)
            and isinstance(item.get("from_category_id"), str | None)
        ):
            return _api_error(400, "bad_input", "each assignment needs episode_id, from_category_id and to_key")

    referenced = {item["to_key"] for item in assignments}
    new_names: dict[str, str] = {}
    for item in new_categories:
        if not (isinstance(item, dict) and isinstance(item.get("key"), str) and isinstance(item.get("name"), str)):
            return _api_error(400, "bad_input", "each new category needs key and name")
        try:
            new_names[item["key"]] = validate_name(item["name"])
        except CategoryNameError as error:
            return _name_error(error)

    repo = CategoryRepo(session)
    targets: dict[str, str] = {}  # to_key -> category id
    created: list[dict[str, Any]] = []
    try:
        for key, name in new_names.items():
            if key not in referenced:
                continue  # the user rejected this category as a whole
            existing = repo.get_by_key(name_key(name))
            category = existing or repo.create(name, origin="ai")
            targets[key] = category.id
            created.append(
                {"key": key, "category_id": category.id, "name": category.name, "reused": existing is not None}
            )

        applied = 0
        skipped: list[dict[str, str]] = []
        for item in assignments:
            to_key: str = item["to_key"]
            target_id = targets.get(to_key)
            if target_id is None and to_key.startswith("c:") and repo.get(to_key[2:]) is not None:
                target_id = to_key[2:]
            episode = session.get(Episode, item["episode_id"])
            reason = apply_decision(
                episode_exists=episode is not None,
                current_category_id=episode.category_id if episode else None,
                current_origin=episode.category_origin if episode else None,
                from_category_id=item["from_category_id"],
                target_exists=target_id is not None,
            )
            if reason is not None:
                skipped.append({"episode_id": item["episode_id"], "reason": reason})
                continue
            repo.assign(item["episode_id"], target_id, "auto")
            applied += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return JSONResponse(content={"created": created, "applied": applied, "skipped": skipped})


@router.patch("/categories/{category_id}")
async def rename_category(
    category_id: str, body: dict[str, Any], session: Session = SESSION_DEP
) -> JSONResponse:
    name = body.get("name")
    if not isinstance(name, str):
        return _api_error(400, "bad_input", "name must be a string")
    repo = CategoryRepo(session)
    category = repo.get(category_id)
    if category is None:
        return _api_error(404, "not_found", "category not found")
    try:
        repo.rename(category, name)
    except CategoryNameError as error:
        return _name_error(error)
    except DuplicateCategory as error:
        return _duplicate(error)
    session.commit()
    return JSONResponse(content=_category_payload(category, repo.counts().get(category.id, 0)))


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, session: Session = SESSION_DEP) -> JSONResponse:
    repo = CategoryRepo(session)
    category = repo.get(category_id)
    if category is None:
        return _api_error(404, "not_found", "category not found")
    released = repo.delete(category)
    session.commit()
    return JSONResponse(content={"released": released})


# ------------------------------------------------------------------- AI runs


@router.post("/categorize")
async def start_categorize(request: Request) -> JSONResponse:
    runner: CategorizeRunner = request.app.state.categorize_runner
    try:
        run = runner.start()
    except RunInProgress as error:
        return _api_error(409, "conflict", str(error), {"run_id": error.run_id})
    except NothingToCategorize as error:
        return _api_error(400, "bad_input", str(error))
    return JSONResponse(status_code=202, content={"run_id": run.run_id, "state": run.state})


@router.get("/categorize/{run_id}")
async def get_categorize(request: Request, run_id: str) -> JSONResponse:
    run = request.app.state.categorize_runner.get(run_id)
    if run is None:
        return _api_error(404, "not_found", "categorisation run not found")
    return JSONResponse(content=run.payload())


@router.delete("/categorize/{run_id}")
async def cancel_categorize(request: Request, run_id: str) -> JSONResponse:
    run = request.app.state.categorize_runner.cancel(run_id)
    if run is None:
        return _api_error(404, "not_found", "categorisation run not found")
    return JSONResponse(content={"state": run.state})


# ------------------------------------------------------------------- helpers


def _category_list(session: Session) -> dict[str, Any]:
    repo = CategoryRepo(session)
    counts = repo.counts()
    return {
        "items": [_category_payload(category, counts.get(category.id, 0)) for category in repo.list_ordered()],
        "uncategorized_count": repo.uncategorized_count(),
    }


def _category_payload(category: Category, episode_count: int) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "position": category.position,
        "origin": category.origin,
        "episode_count": episode_count,
    }


def _name_error(error: CategoryNameError) -> JSONResponse:
    return _api_error(400, "bad_input", str(error), {"reason": error.reason})


def _duplicate(error: DuplicateCategory) -> JSONResponse:
    return _api_error(409, "conflict", str(error), {"category_id": error.existing_id})
