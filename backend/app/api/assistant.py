from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..assistant.service import AssistantService
from ..db.repositories import Repository
from ..domain.schemas import AssistantAction, AssistantMessageCreate
from .dependencies import get_model_adapter, get_repository

router = APIRouter(prefix="/api/projects/{project_id}/assistant", tags=["assistant"])


class AssistantActionsApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: list[AssistantAction] = Field(min_length=1, max_length=20)


def _service(repository: Repository, model_adapter) -> AssistantService:
    return AssistantService(repository, model_adapter)


@router.get("/session")
def get_session(
    project_id: str,
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
):
    return _service(repository, model_adapter).session(project_id)


@router.post("/messages", status_code=201)
async def create_message(
    project_id: str,
    payload: AssistantMessageCreate,
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
):
    return await _service(repository, model_adapter).reply(project_id, payload.content)


@router.post("/actions:apply")
async def apply_actions(
    project_id: str,
    payload: AssistantActionsApply,
    request: Request,
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
):
    results = _service(repository, model_adapter).apply_actions(project_id, payload.actions)
    for result in results:
        run_id = result.get("generation_run_id")
        if run_id:
            for item in repository.list_items(run_id=str(run_id)):
                await request.app.state.generation_worker.enqueue(item["id"])
    return {"results": results}
