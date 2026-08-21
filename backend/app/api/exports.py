from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..db.repositories import Repository
from ..domain.errors import DomainError
from ..export.protocol import ExportRow
from ..export.service import ExportService
from .dependencies import get_repository

router = APIRouter(tags=["exports"])


class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    export_run_id: str | None = None
    generation_run_id: str | None = None
    sheet_title: str = Field(default="小红书文案输出", min_length=1, max_length=100)


def _resolve_generation_run(
    repository: Repository, project_id: str, generation_run_id: str | None
) -> str:
    if generation_run_id:
        run = repository.get_run(generation_run_id)
        if run["project_id"] != project_id:
            raise DomainError(
                "RUN_NOT_FOUND", "Generation run not found", status_code=404
            )
        return generation_run_id
    visible_runs = repository.list_generation_runs(project_id)
    if not visible_runs:
        raise DomainError(
            "VISIBLE_GENERATION_RUN_REQUIRED",
            "No visible generation batch is available for export",
        )
    return visible_runs[0]["id"]


def _public_export(run: dict, adapter: str) -> dict:
    return {
        **run,
        "adapter": adapter,
        "safe_error": run.get("error_code"),
    }


def _completed_rows(
    repository: Repository,
    project_id: str,
    generation_run_id: str | None,
) -> list[ExportRow]:
    type_names = {row["id"]: row["name"] for row in repository.list_copy_types(project_id)}
    items = repository.list_items(project_id=project_id)
    if generation_run_id:
        items = [item for item in items if item["run_id"] == generation_run_id]
    rows: list[ExportRow] = []
    for item in items:
        if item["workflow_status"] != "completed" or not item["content"]:
            continue
        force_event = repository.latest_review_event(item["id"], "force_pass")
        legacy_issues = json.loads(force_event["legacy_issues_json"]) if force_event else []
        content = item["content"]
        rows.append(
            ExportRow(
                ordinal=len(rows) + 1,
                item_id=item["id"],
                copy_type=type_names.get(item["copy_type_id"], ""),
                title=content["title"],
                body=content["body"],
                tags=json.loads(content["tags_json"]),
                completion_reason=item["completion_reason"],
                legacy_issues=legacy_issues,
                change_note=content["change_note"],
            )
        )
    return rows


async def _execute_export(
    request: Request,
    repository: Repository,
    run: dict,
) -> dict:
    exporter = request.app.state.exporter
    if exporter is None:
        raise DomainError(
            "FEISHU_NOT_CONFIGURED", "Feishu export is not configured", status_code=503
        )
    rows = _completed_rows(
        repository,
        run["project_id"],
        run["generation_run_id"],
    )
    return await ExportService(repository, exporter).export_completed(
        export_run_id=run["id"],
        project_id=run["project_id"],
        sheet_title=run["sheet_title"],
        rows=rows,
        generation_run_id=run["generation_run_id"],
    )


@router.get("/api/projects/{project_id}/exports")
def list_exports(
    project_id: str,
    request: Request,
    repository: Repository = Depends(get_repository),
):
    repository.get_project(project_id)
    adapter = getattr(request.app.state.exporter, "adapter_name", "feishu")
    return [_public_export(run, adapter) for run in repository.list_export_runs(project_id)]


@router.post("/api/projects/{project_id}/exports", status_code=201)
async def create_export(
    project_id: str,
    payload: ExportCreate,
    request: Request,
    repository: Repository = Depends(get_repository),
):
    repository.get_project(project_id)
    export_id = payload.export_run_id or str(uuid4())
    generation_run_id = _resolve_generation_run(
        repository, project_id, payload.generation_run_id
    )
    run = repository.create_export_run(
        export_id,
        project_id,
        payload.sheet_title,
        generation_run_id,
    )
    result = await _execute_export(request, repository, run)
    return _public_export(result, getattr(request.app.state.exporter, "adapter_name", "feishu"))


@router.get("/api/export-runs/{export_id}")
def get_export(
    export_id: str,
    request: Request,
    repository: Repository = Depends(get_repository),
):
    return _public_export(
        repository.get_export_run(export_id),
        getattr(request.app.state.exporter, "adapter_name", "feishu"),
    )


@router.post("/api/export-runs/{export_id}:retry")
async def retry_export(
    export_id: str,
    request: Request,
    repository: Repository = Depends(get_repository),
):
    result = await _execute_export(request, repository, repository.get_export_run(export_id))
    return _public_export(result, getattr(request.app.state.exporter, "adapter_name", "feishu"))
