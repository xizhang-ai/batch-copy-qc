from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ..brief.service import BriefService
from ..brief.storage import save_upload
from ..db.repositories import Repository
from ..domain.enums import BriefScope
from ..domain.errors import DomainError
from ..qc.materialize import materialize_brief_qc_rules
from .dependencies import get_model_adapter, get_repository, get_settings_dependency

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=200)
    brand: str = ""
    category: str = ""


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = Field(None, min_length=1, max_length=200)
    category: str | None = None
    brand: str | None = None
    product_sku: str | None = None
    project_content: dict[str, Any] | None = None
    copy_requirements: dict[str, Any] | None = None
    qc_requirements: dict[str, Any] | None = None
    pending_confirmation: list[Any] | None = None
    findings: list[dict[str, Any]] | None = None
    confirmed: bool | None = None


def _project(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if not key.endswith("_json")}
    for field in (
        "project_content",
        "copy_requirements",
        "qc_requirements",
        "pending_confirmation",
    ):
        result[field] = json.loads(row[f"{field}_json"])
    result["confirmed"] = bool(result["confirmed"])
    result["status"] = "confirmed" if result["confirmed"] else "draft"
    result["structured"] = {
        "project_content": result["project_content"],
        "copy_requirements": result["copy_requirements"],
        "qc_requirements": result["qc_requirements"],
        "pending_confirmation": result["pending_confirmation"],
    }
    return result


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, repository: Repository = Depends(get_repository)):
    return _project(
        repository.create_project(
            payload.name.strip(),
            brand=payload.brand.strip(),
            category=payload.category.strip(),
        )
    )


@router.get("")
def list_projects(repository: Repository = Depends(get_repository)):
    return [_project(row) for row in repository.list_projects()]


@router.get("/{project_id}")
def get_project(project_id: str, repository: Repository = Depends(get_repository)):
    return _project(repository.get_project(project_id))


@router.patch("/{project_id}")
def patch_project(
    payload: ProjectUpdate, project_id: str, repository: Repository = Depends(get_repository)
):
    data = payload.model_dump(exclude_unset=True)
    qc_findings: list[dict[str, Any]] = []
    if "findings" in data:
        findings = data.pop("findings") or []
        qc_findings = [row for row in findings if row.get("section") == "qc_requirements"]
        grouped = {
            "project_content_json": {
                "findings": [row for row in findings if row.get("section") == "project_content"]
            },
            "copy_requirements_json": {
                "findings": [row for row in findings if row.get("section") == "copy_requirements"]
            },
            "qc_requirements_json": {
                "findings": [row for row in findings if row.get("section") == "qc_requirements"]
            },
            "pending_confirmation_json": [
                row for row in findings if row.get("section") == "needs_confirmation"
            ],
        }
        data.update(grouped)
    for field in (
        "project_content",
        "copy_requirements",
        "qc_requirements",
        "pending_confirmation",
    ):
        if field in data:
            data[f"{field}_json"] = data.pop(field)
    updated = repository.update_project(project_id, data)
    if updated["confirmed"]:
        if not qc_findings:
            raw_qc = data.get("qc_requirements_json", updated["qc_requirements_json"])
            if isinstance(raw_qc, str):
                raw_qc = json.loads(raw_qc)
            if isinstance(raw_qc, dict):
                qc_findings = list(raw_qc.get("findings", []))
        materialize_brief_qc_rules(repository, project_id, qc_findings)
    return _project(updated)


@router.post("/{project_id}/briefs:parse")
async def parse_project_brief(
    project_id: str,
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
    settings=Depends(get_settings_dependency),
):
    repository.get_project(project_id)
    if (text is None) == (file is None):
        raise DomainError("BRIEF_INPUT_EXCLUSIVE", "Provide exactly one of text or file")
    service = BriefService(repository, model_adapter)
    if file is None:
        return await service.parse_text(project_id, text or "")
    if repository.count_brief_sources(project_id) >= 20:
        raise DomainError("BRIEF_ATTACHMENT_LIMIT", "A project supports at most 20 attachments")
    display_name, path, _size = await save_upload(file, settings.upload_dir / project_id)
    return await service.parse_file(
        project_id,
        str(path),
        scope=BriefScope.PROJECT,
        display_name=display_name,
        stored_name=path.name,
    )
