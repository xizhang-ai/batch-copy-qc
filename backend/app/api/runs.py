from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from ..db.repositories import Repository
from ..generation.service import GenerationService
from .dependencies import get_repository

router = APIRouter(tags=["generation-runs"])


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str | None = None


@router.post("/api/projects/{project_id}/generation-runs", status_code=201)
async def create_run(
    project_id: str,
    request: Request,
    payload: RunCreate | None = None,
    repository: Repository = Depends(get_repository),
):
    run, items = GenerationService(repository).create_run(
        project_id, run_id=payload.run_id if payload else None
    )
    worker = request.app.state.generation_worker
    for item in items:
        await worker.enqueue(item["id"])
    return GenerationService(repository).summary(run["id"])


@router.get("/api/generation-runs/{run_id}")
def get_run(run_id: str, repository: Repository = Depends(get_repository)):
    return GenerationService(repository).summary(run_id)
