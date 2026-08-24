from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from ..db.repositories import Repository
from ..domain.schemas import PreviewConfirmation
from ..generation.service import GenerationService
from .dependencies import get_repository

router = APIRouter(tags=["generation-runs"])


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str | None = None
    generation_mode: Literal["preview", "full"] = "full"


class RunUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archived: bool


def _public_run(run: dict):
    return {
        **run,
        "total_requested": run.get("total_requested", run.get("requested_count", 0)),
        "label": f"第 {run['batch_number']} 批",
        "archived": bool(run["archived"]),
        "generation_mode": run.get("generation_mode", "full"),
        "generation_phase": run.get("generation_phase", "full_running"),
        "preview_item_count": run.get("preview_item_count", 0),
    }


@router.post("/api/projects/{project_id}/generation-runs", status_code=201)
async def create_run(
    project_id: str,
    request: Request,
    payload: RunCreate | None = None,
    repository: Repository = Depends(get_repository),
):
    run, items = GenerationService(repository).create_run(
        project_id,
        run_id=payload.run_id if payload else None,
        generation_mode=payload.generation_mode if payload else "full",
    )
    worker = request.app.state.generation_worker
    for item in items:
        await worker.enqueue(item["id"])
    return _public_run(GenerationService(repository).summary(run["id"]))


@router.post("/api/generation-runs/{run_id}/preview:confirm")
async def confirm_preview(
    run_id: str,
    payload: PreviewConfirmation,
    request: Request,
    repository: Repository = Depends(get_repository),
):
    run, items = GenerationService(repository).confirm_preview(
        run_id, payload.expected_preview_item_count
    )
    worker = request.app.state.generation_worker
    for item in items:
        await worker.enqueue(item["id"])
    return _public_run(GenerationService(repository).summary(run["id"]))


@router.get("/api/generation-runs/{run_id}")
def get_run(run_id: str, repository: Repository = Depends(get_repository)):
    return _public_run(GenerationService(repository).summary(run_id))


@router.get("/api/projects/{project_id}/generation-runs")
def list_runs(
    project_id: str,
    include_archived: bool = False,
    repository: Repository = Depends(get_repository),
):
    service = GenerationService(repository)
    return [
        _public_run(service.summary(run["id"]))
        for run in repository.list_generation_runs(
            project_id, include_archived=include_archived
        )
    ]


@router.patch("/api/generation-runs/{run_id}")
def update_run(
    run_id: str,
    payload: RunUpdate,
    repository: Repository = Depends(get_repository),
):
    run = repository.set_generation_run_archived(run_id, payload.archived)
    return _public_run(run)
