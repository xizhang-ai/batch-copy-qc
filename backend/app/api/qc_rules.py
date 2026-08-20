from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..db.repositories import Repository
from ..domain.errors import DomainError
from .dependencies import get_repository

router = APIRouter(tags=["qc-rules"])


class RuleCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scope: str = Field(pattern="^(project|type|copy_type)$")
    level: str = Field(pattern="^(hard|soft)$")
    category: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    copy_type_id: str | None = None
    source_evidence: str = ""
    source_kind: str | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.scope == "project") != (self.copy_type_id is None):
            raise ValueError("copy_type_id must match rule scope")
        return self


class RuleUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    level: str | None = Field(None, pattern="^(hard|soft)$")
    category: str | None = Field(None, min_length=1)
    statement: str | None = Field(None, min_length=1)
    source_evidence: str | None = None
    enabled: bool | None = None


@router.get("/api/projects/{project_id}/qc-rules")
def list_rules(
    project_id: str,
    copy_type_id: str | None = None,
    repository: Repository = Depends(get_repository),
):
    return [_public_rule(rule) for rule in repository.list_rules(project_id, copy_type_id)]


@router.post("/api/projects/{project_id}/qc-rules", status_code=201)
def create_rule(
    project_id: str, payload: RuleCreate, repository: Repository = Depends(get_repository)
):
    repository.get_project(project_id)
    values = payload.model_dump()
    values["scope"] = "copy_type" if values["scope"] == "type" else values["scope"]
    if values["copy_type_id"]:
        copy_type = repository.get_copy_type(values["copy_type_id"])
        if copy_type["project_id"] != project_id:
            raise DomainError(
                "COPY_TYPE_PROJECT_MISMATCH",
                "Copy type does not belong to the requested project",
                status_code=409,
            )
    if not values["source_kind"]:
        values["source_kind"] = (
            "explicit_project_qc" if values["scope"] == "project" else "explicit_type_qc"
        )
    return _public_rule(repository.create_rule(project_id, **values))


@router.patch("/api/qc-rules/{rule_id}")
def update_rule(
    rule_id: str, payload: RuleUpdate, repository: Repository = Depends(get_repository)
):
    return _public_rule(repository.update_rule(rule_id, payload.model_dump(exclude_unset=True)))


@router.delete("/api/qc-rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, repository: Repository = Depends(get_repository)):
    repository.delete_rule(rule_id)


def _public_rule(rule: dict) -> dict:
    return {
        **rule,
        "scope": "type" if rule["scope"] == "copy_type" else rule["scope"],
        "enabled": bool(rule["enabled"]),
    }
