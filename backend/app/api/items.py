from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from ..db.repositories import Repository
from ..domain.errors import DomainError
from ..qc.service import QcService
from ..review.service import ReviewService
from .dependencies import get_model_adapter, get_repository, get_request_qc_service

router = APIRouter(tags=["items"])


class ItemEdit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    expected_version: int = Field(
        ge=1, validation_alias=AliasChoices("expected_version", "version")
    )
    title: str
    body: str
    tags: list[str]
    change_note: str = ""


class SelectionRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    field: Literal["title", "body"]
    selection_start: int = Field(ge=0)
    selection_end: int = Field(gt=0)
    selected_text: str = Field(min_length=1)
    instruction: str = Field(min_length=1)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["reject", "pass", "force_pass", "recall"]
    reason: str = ""
    legacy_issues: list[str] = Field(default_factory=list)

    @field_validator("legacy_issues", mode="before")
    @classmethod
    def normalize_legacy_issues(cls, value):
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            if any(not isinstance(issue, str) or not issue.strip() for issue in value):
                raise ValueError("legacy issues must contain non-empty strings")
            return [issue.strip() for issue in value]
        return value


def _item(row):
    result = {key: value for key, value in row.items() if key != "content"}
    if row["content"]:
        result["content"] = {**row["content"], "tags": json.loads(row["content"]["tags_json"])}
        result["content"].pop("tags_json", None)
        result["title"] = result["content"]["title"]
        result["body"] = result["content"]["body"]
        result["tags"] = result["content"]["tags"]
    else:
        result["content"] = None
        result.update({"title": "", "body": "", "tags": []})
    result["version"] = result["current_version"]
    return result


def _full_item(row, repository: Repository):
    result = _item(row)
    result["findings"] = repository.unresolved_findings(row["id"])
    result["copy_type_name"] = repository.get_copy_type(row["copy_type_id"])["name"]
    return result


@router.get("/api/items/{item_id}")
def get_item(item_id: str, repository: Repository = Depends(get_repository)):
    return _full_item(repository.get_item(item_id), repository)


@router.patch("/api/items/{item_id}")
async def edit_item(
    item_id: str,
    payload: ItemEdit,
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
    qc_service: QcService = Depends(get_request_qc_service),
):
    return _full_item(
        await ReviewService(repository, model_adapter, qc_service).edit(
            item_id, **payload.model_dump()
        ),
        repository,
    )


@router.post("/api/items/{item_id}/rewrite-selection")
async def rewrite_selection(
    item_id: str,
    payload: SelectionRewrite,
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
    qc_service: QcService = Depends(get_request_qc_service),
):
    return _full_item(
        await ReviewService(repository, model_adapter, qc_service).rewrite_selection(
            item_id, **payload.model_dump()
        ),
        repository,
    )


@router.post("/api/items/{item_id}/review")
def review(
    item_id: str,
    payload: ReviewDecision,
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
):
    return _item(ReviewService(repository, model_adapter).decide(item_id, **payload.model_dump()))


@router.post("/api/items/{item_id}/qc:retry")
async def retry_qc(
    item_id: str,
    request: Request,
    repository: Repository = Depends(get_repository),
    qc_service: QcService = Depends(get_request_qc_service),
):
    item = repository.get_item(item_id)
    retryable = {
        "MODEL_RATE_LIMITED",
        "MODEL_TIMEOUT",
        "MODEL_UNAVAILABLE",
        "MODEL_RESPONSE_INVALID",
        "GENERATION_FAILED",
    }
    if item["workflow_status"] != "human_review" or item["error_code"] not in retryable:
        raise DomainError(
            "ITEM_RETRY_NOT_ALLOWED",
            "Only retryable system failures can be retried",
            status_code=409,
        )
    updated = repository.cas_item_state(item_id, "human_review", "pending_ai_qc", error_code=None)
    if item["generation_status"] != "generated" or item["content"] is None:
        repository.connection.execute(
            "UPDATE copy_items SET generation_status='queued' WHERE id=?", (item_id,)
        )
        repository.connection.commit()
        await request.app.state.generation_worker.enqueue(item_id)
        return _item(repository.get_item(updated["id"]))
    await qc_service.run(item_id)
    return _item(repository.get_item(updated["id"]))


@router.get("/api/projects/{project_id}/board")
def board(
    project_id: str,
    run_id: str | None = None,
    copy_type_id: str | None = None,
    completion_reason: str | None = None,
    repository: Repository = Depends(get_repository),
):
    items = repository.list_items(project_id=project_id)
    if run_id:
        items = [item for item in items if item["run_id"] == run_id]
    if copy_type_id:
        items = [item for item in items if item["copy_type_id"] == copy_type_id]
    if completion_reason:
        items = [item for item in items if item["completion_reason"] == completion_reason]
    type_names = {row["id"]: row["name"] for row in repository.list_copy_types(project_id)}
    keys = ["pending_ai_qc", "ai_qc_running", "ai_rewrite_running", "human_review", "completed"]
    columns = {key: {"count": 0, "items": []} for key in keys}
    flat_items = []
    for item in items:
        findings = repository.unresolved_findings(item["id"])
        matches = [finding["matched_id"] for finding in findings if finding["matched_id"]]
        content = item["content"]
        card = {
            "item_id": item["id"],
            "copy_type": type_names.get(item["copy_type_id"], ""),
            "title_preview": content["title"][:60] if content else "",
            "workflow_status": item["workflow_status"],
            "completion_reason": item["completion_reason"],
            "issue_count": len(findings),
            "similar_item_ids": matches,
            "modification_count": max(item["current_version"] - 1, 0),
            "updated_at": item["updated_at"],
        }
        columns[item["workflow_status"]]["items"].append(card)
        columns[item["workflow_status"]]["count"] += 1
        public = _item(item)
        public["copy_type_name"] = type_names.get(item["copy_type_id"], "")
        public["findings"] = findings
        flat_items.append(public)
    active_run_id = run_id or (items[-1]["run_id"] if items else "")
    run_status = "idle"
    if active_run_id:
        raw_status = repository.get_run(active_run_id)["status"]
        run_status = "running" if raw_status in {"queued", "running"} else "completed"
    return {
        "project_id": project_id,
        "run_id": active_run_id,
        "run_status": run_status,
        "items": flat_items,
        "updated_at": max((item["updated_at"] for item in items), default=""),
        "columns": columns,
        "stats": {
            "total": len(items),
            "pending": columns["pending_ai_qc"]["count"],
            "ai_processing": columns["ai_qc_running"]["count"]
            + columns["ai_rewrite_running"]["count"],
            "human_review": columns["human_review"]["count"],
            "completed": columns["completed"]["count"],
        },
    }
