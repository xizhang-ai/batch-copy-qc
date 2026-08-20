from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ..brief.service import BriefService
from ..brief.storage import save_upload
from ..db.repositories import Repository
from ..domain.enums import BriefScope
from ..domain.errors import DomainError
from ..domain.schemas import ReferenceExample, ReferenceExamplesContext
from ..qc.materialize import materialize_brief_qc_rules
from .dependencies import get_model_adapter, get_repository, get_settings_dependency

router = APIRouter(tags=["copy-types"])


class CopyTypeCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(default="", max_length=100)
    quantity: int = Field(default=1, ge=1, le=100)
    brief_text: str = ""
    use_reference_examples: bool = False
    use_description_requirements: bool = False
    description_requirements: dict[str, Any] = Field(default_factory=dict)
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)


class BriefReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    section: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_quote: str = ""
    confidence: float = Field(ge=0, le=1)
    decision: Literal["pending", "confirmed", "ignored"] = "pending"


class BriefReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_change_suggestions: list[BriefReviewItem] = Field(default_factory=list)
    conflicts: list[BriefReviewItem] = Field(default_factory=list)


class CopyTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = Field(None, min_length=1, max_length=100)
    quantity: int | None = Field(None, ge=1, le=100)
    brief_text: str | None = None
    use_reference_examples: bool | None = None
    use_description_requirements: bool | None = None
    description_requirements: dict[str, Any] | None = None
    must_include: list[str] | None = None
    must_avoid: list[str] | None = None
    style_profile: dict[str, Any] | None = None
    style_profile_confirmed: bool | None = None
    type_brief: str | None = None
    requirements: dict[str, Any] | None = None
    input_modes: list[str] | None = None
    reference_profile: dict[str, Any] | None = None
    brief_review: BriefReview | None = None


class ReferenceCreate(ReferenceExample):
    pass


class ReferenceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    raw_text: str
    title: str = ""
    body: str = ""
    topics: list[str] = Field(default_factory=list)


class ReferenceAnalyze(BaseModel):
    model_config = ConfigDict(extra="ignore")
    examples: list[ReferenceInput] | None = Field(None, min_length=1, max_length=5)


class BriefAssignment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    copy_type_id: str | None = None
    confirmed: bool = True


_REQUIREMENT_KEYS = {
    "标题": "title_direction",
    "title": "title_direction",
    "结构": "body_structure",
    "正文": "body_structure",
    "structure": "body_structure",
    "语气": "tone",
    "tone": "tone",
    "人设": "persona",
    "人群": "persona",
    "persona": "persona",
    "场景": "scenario",
    "scene": "scenario",
    "话题": "topic_requirements",
    "标签": "topic_requirements",
    "topic": "topic_requirements",
}


def _copy_type_brief_patch(parsed: dict[str, Any]) -> dict[str, Any]:
    def review_item(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(raw.get("id") or uuid4()),
            "section": str(raw.get("section") or "unclassified"),
            "value": str(raw.get("value") or "").strip(),
            "source_quote": str(raw.get("source_quote") or raw.get("evidence") or ""),
            "confidence": float(raw.get("confidence", 0.0)),
            "decision": str(raw.get("decision") or "pending"),
        }

    parsed_qc = parsed.get("sections", {}).get("project_qc", [])
    brief_review = {
        "project_change_suggestions": [
            review_item(row) for row in parsed.get("project_change_suggestions", [])
        ],
        "conflicts": [review_item(row) for row in [*parsed_qc, *parsed.get("conflicts", [])]],
    }
    structured = parsed.get("copy_type_fields")
    if structured is not None:
        requirements = {
            key: structured.get(key, "")
            for key in (
                "title_direction",
                "body_structure",
                "tone",
                "persona",
                "scenario",
                "topic_requirements",
            )
        }
        return {
            **parsed,
            "requirements": requirements,
            "must_include": structured.get("must_include", []),
            "must_avoid": structured.get("must_avoid", []),
            "sources": ["brief"],
            "parsed_finding_count": len(parsed.get("findings", [])),
            "project_change_suggestions": parsed.get("project_change_suggestions", []),
            "conflicts": parsed.get("conflicts", []),
            "brief_review": brief_review,
        }
    requirements = {
        "title_direction": "",
        "body_structure": "",
        "tone": "",
        "persona": "",
        "scenario": "",
        "topic_requirements": "",
    }
    must_include: list[str] = []
    must_avoid: list[str] = []
    project_suggestions: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for finding in parsed.get("findings", []):
        section = finding.get("section")
        if section == "project_content":
            project_suggestions.append(finding)
            continue
        if section == "needs_confirmation":
            conflicts.append(finding)
            continue
        label = str(finding.get("label", "")).lower()
        value = str(finding.get("value", "")).strip()
        if not value:
            continue
        if any(token in label for token in ("一定要有", "必含", "must_include")):
            must_include.append(value)
            continue
        if any(token in label for token in ("一定不要", "禁止", "禁用", "must_avoid")):
            must_avoid.append(value)
            continue
        key = next((target for token, target in _REQUIREMENT_KEYS.items() if token in label), None)
        if key:
            requirements[key] = "\n".join(filter(None, (requirements[key], value)))
        else:
            conflicts.append(finding)

    return {
        **parsed,
        "requirements": requirements,
        "must_include": must_include,
        "must_avoid": must_avoid,
        "sources": ["brief"],
        "parsed_finding_count": len(parsed.get("findings", [])),
        "project_change_suggestions": project_suggestions,
        "conflicts": conflicts,
        "brief_review": brief_review,
    }


def _copy_type(row: dict[str, Any], repository: Repository) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if not key.endswith("_json")}
    for field in ("description_requirements", "must_include", "must_avoid", "style_profile"):
        value = row.get(f"{field}_json")
        result[field] = json.loads(value) if value else (None if field == "style_profile" else {})
    raw_brief_review = row.get("brief_review_json")
    result["brief_review"] = (
        json.loads(raw_brief_review)
        if raw_brief_review
        else {"project_change_suggestions": [], "conflicts": []}
    )
    if not isinstance(result["brief_review"], dict):
        result["brief_review"] = {"project_change_suggestions": [], "conflicts": []}
    for field in (
        "use_reference_examples",
        "use_description_requirements",
        "style_profile_confirmed",
    ):
        result[field] = bool(result[field])
    result["sources"] = ["manual"]
    if result["brief_text"]:
        result["sources"].append("brief")
    if result["use_reference_examples"]:
        result["sources"].append("reference")
    result["input_modes"] = []
    if result["use_reference_examples"]:
        result["input_modes"].append("reference_examples")
    if result["use_description_requirements"]:
        result["input_modes"].append("description_requirements")
    result["type_brief"] = result["brief_text"]
    result["requirements"] = result["description_requirements"]
    result["references"] = [
        {
            **reference,
            "topics": json.loads(reference["topics_json"]),
        }
        for reference in repository.list_references(row["id"])
    ]
    if result["style_profile"]:
        profile = result["style_profile"]
        result["reference_profile"] = {
            "title_hook": profile.get("hook_pattern", ""),
            "structure_rhythm": profile.get("structure", ""),
            "point_of_view": profile.get("narrative_perspective", ""),
            "tone": profile.get("tone", ""),
            "persona": profile.get("persona", ""),
            "scenario": profile.get("scenes", ""),
            "information_density": profile.get("information_density", ""),
            "ending": profile.get("ending_strategy", ""),
            "topic_strategy": profile.get("tag_strategy", ""),
            "source_facts": profile.get("source_facts_to_exclude", []),
            "avoid_expressions": profile.get("expressions_to_avoid", []),
            "confirmed": result["style_profile_confirmed"],
        }
    return result


def _materialize_derived_rules(
    repository: Repository, project_id: str, copy_type: dict[str, Any]
) -> None:
    existing = {
        (rule["category"], rule["statement"].strip())
        for rule in repository.list_rules(project_id)
        if rule["copy_type_id"] == copy_type["id"]
    }
    for phrase in json.loads(copy_type["must_include_json"]):
        key = ("must_include", f"必含：{phrase}")
        if key in existing:
            continue
        repository.create_rule(
            project_id,
            copy_type_id=copy_type["id"],
            scope="copy_type",
            level="soft",
            category="must_include",
            statement=f"必含：{phrase}",
            source_kind="derived_type_constraint",
        )
        existing.add(key)
    for phrase in json.loads(copy_type["must_avoid_json"]):
        key = ("must_avoid", f"禁用：{phrase}")
        if key in existing:
            continue
        repository.create_rule(
            project_id,
            copy_type_id=copy_type["id"],
            scope="copy_type",
            level="hard",
            category="must_avoid",
            statement=f"禁用：{phrase}",
            source_kind="derived_type_constraint",
        )
        existing.add(key)


@router.get("/api/projects/{project_id}/copy-types")
def list_copy_types(project_id: str, repository: Repository = Depends(get_repository)):
    repository.get_project(project_id)
    return [_copy_type(row, repository) for row in repository.list_copy_types(project_id)]


@router.get("/api/copy-types/{copy_type_id}")
def get_copy_type(copy_type_id: str, repository: Repository = Depends(get_repository)):
    return _copy_type(repository.get_copy_type(copy_type_id), repository)


@router.post("/api/projects/{project_id}/copy-types", status_code=201)
def create_copy_type(
    project_id: str, payload: CopyTypeCreate, repository: Repository = Depends(get_repository)
):
    repository.get_project(project_id)
    row = repository.create_copy_type(project_id, **payload.model_dump())
    _materialize_derived_rules(repository, project_id, row)
    return _copy_type(row, repository)


@router.patch("/api/copy-types/{copy_type_id}")
def update_copy_type(
    copy_type_id: str, payload: CopyTypeUpdate, repository: Repository = Depends(get_repository)
):
    row = repository.get_copy_type(copy_type_id)
    data = payload.model_dump(exclude_unset=True)
    review_for_rules: dict[str, Any] | None = None
    if "type_brief" in data:
        data["brief_text"] = data.pop("type_brief")
    if "requirements" in data:
        data["description_requirements_json"] = data.pop("requirements")
    if "input_modes" in data:
        input_modes = data.pop("input_modes") or []
        data["use_reference_examples"] = "reference_examples" in input_modes
        data["use_description_requirements"] = "description_requirements" in input_modes
    if "reference_profile" in data:
        profile = data.pop("reference_profile") or {}
        data["style_profile_json"] = {
            "hook_pattern": profile.get("title_hook", ""),
            "opening_style": "",
            "structure": profile.get("structure_rhythm", ""),
            "narrative_perspective": profile.get("point_of_view", ""),
            "tone": profile.get("tone", ""),
            "persona": profile.get("persona", ""),
            "scenes": profile.get("scenario", ""),
            "information_density": profile.get("information_density", ""),
            "selling_point_order": "",
            "ending_strategy": profile.get("ending", ""),
            "tag_strategy": profile.get("topic_strategy", ""),
            "source_facts_to_exclude": profile.get("source_facts", []),
            "expressions_to_avoid": profile.get("avoid_expressions", []),
        }
        data["style_profile_confirmed"] = bool(profile.get("confirmed"))
    if "brief_review" in data:
        review = data.pop("brief_review")
        review_for_rules = (
            review.model_dump(mode="json") if hasattr(review, "model_dump") else review
        )
        data["brief_review_json"] = review_for_rules or {
            "project_change_suggestions": [],
            "conflicts": [],
        }
    for field in ("description_requirements", "must_include", "must_avoid", "style_profile"):
        if field in data:
            data[f"{field}_json"] = data.pop(field)
    updated = repository.update_copy_type(copy_type_id, data)
    _materialize_derived_rules(repository, row["project_id"], updated)
    if review_for_rules:
        qc_sections = {"claim", "must_avoid", "project_qc", "type_qc", "qc_requirement"}
        confirmed_qc = [
            finding
            for finding in review_for_rules.get("conflicts", [])
            if finding.get("decision") == "confirmed" and finding.get("section") in qc_sections
        ]
        materialize_brief_qc_rules(
            repository,
            row["project_id"],
            confirmed_qc,
            scope="copy_type",
            copy_type_id=copy_type_id,
            source_kind="derived_type_brief",
        )
    return _copy_type(updated, repository)


@router.delete("/api/copy-types/{copy_type_id}", status_code=204)
def delete_copy_type(copy_type_id: str, repository: Repository = Depends(get_repository)):
    repository.delete_copy_type(copy_type_id)


@router.post("/api/copy-types/{copy_type_id}/briefs:parse")
async def parse_copy_type_brief(
    copy_type_id: str,
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
    settings=Depends(get_settings_dependency),
):
    copy_type = repository.get_copy_type(copy_type_id)
    if (text is None) == (file is None):
        raise DomainError("BRIEF_INPUT_EXCLUSIVE", "Provide exactly one of text or file")
    service = BriefService(repository, model_adapter)
    if file is None:
        result = _copy_type_brief_patch(
            await service.parse_text(
                copy_type["project_id"],
                text or "",
                scope=BriefScope.COPY_TYPE,
                copy_type_id=copy_type_id,
            )
        )
        repository.update_copy_type(copy_type_id, {"brief_review_json": result["brief_review"]})
        return result
    if repository.count_brief_sources(copy_type["project_id"]) >= 20:
        raise DomainError("BRIEF_ATTACHMENT_LIMIT", "A project supports at most 20 attachments")
    display_name, path, _size = await save_upload(
        file, settings.upload_dir / copy_type["project_id"]
    )
    result = _copy_type_brief_patch(
        await service.parse_file(
            copy_type["project_id"],
            str(path),
            scope=BriefScope.COPY_TYPE,
            copy_type_id=copy_type_id,
            display_name=display_name,
            stored_name=path.name,
        )
    )
    repository.update_copy_type(copy_type_id, {"brief_review_json": result["brief_review"]})
    return result


@router.post("/api/projects/{project_id}/type-files:classify")
async def classify_type_files(
    project_id: str,
    files: list[UploadFile] = File(...),
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
    settings=Depends(get_settings_dependency),
):
    repository.get_project(project_id)
    if repository.count_brief_sources(project_id) + len(files) > 20:
        raise DomainError("BRIEF_ATTACHMENT_LIMIT", "A project supports at most 20 attachments")
    suggestions = []
    service = BriefService(repository, model_adapter)
    for file in files:
        display_name, path, _size = await save_upload(file, settings.upload_dir / project_id)
        parsed = await service.parse_file(
            project_id,
            str(path),
            scope=BriefScope.COPY_TYPE,
            display_name=display_name,
            stored_name=path.name,
        )
        fields = parsed.get("copy_type_fields") or {}
        signals = [
            fields.get("scenario", ""),
            fields.get("persona", ""),
            fields.get("title_direction", ""),
            fields.get("body_structure", ""),
        ]
        suggested_type = next((str(value).strip() for value in signals if str(value).strip()), "")
        parsed_findings = [
            finding for section in parsed.get("sections", {}).values() for finding in section
        ]
        evidence_finding = next(
            (
                finding
                for finding in parsed_findings
                if finding.get("section")
                in {"scenario", "persona", "title_direction", "body_structure"}
            ),
            parsed_findings[0] if parsed_findings else None,
        )
        evidence = evidence_finding.get("source_quote", "") if evidence_finding else display_name
        numeric_confidence = (
            float(evidence_finding.get("confidence", 0.0)) if evidence_finding else 0.0
        )
        confidence = (
            "high"
            if numeric_confidence >= 0.8
            else "medium"
            if numeric_confidence >= 0.5
            else "low"
        )
        if not suggested_type and evidence_finding:
            suggested_type = str(evidence_finding.get("value", "")).strip()
        classification = {
            "suggested_type": suggested_type,
            "evidence": evidence,
            "confidence": confidence,
            "confirmed": False,
        }
        repository.classify_brief_source(parsed["source_id"], None, classification)
        suggestions.append(
            {
                "id": parsed["source_id"],
                "filename": display_name,
                **classification,
            }
        )
    return suggestions


@router.get("/api/projects/{project_id}/type-files")
def list_classified_type_files(
    project_id: str,
    repository: Repository = Depends(get_repository),
):
    repository.get_project(project_id)
    result = []
    for source in repository.list_classified_brief_sources(project_id):
        classification = json.loads(source["classification_json"])
        result.append(
            {
                "id": source["id"],
                "filename": source["display_name"],
                "suggested_type": classification.get("suggested_type", ""),
                "evidence": classification.get("evidence", ""),
                "confidence": classification.get("confidence", "low"),
                "assigned_type_id": source["copy_type_id"]
                or classification.get("assigned_type_id"),
            }
        )
    return result


@router.patch("/api/brief-sources/{brief_source_id}")
def assign_brief_source(
    brief_source_id: str, payload: BriefAssignment, repository: Repository = Depends(get_repository)
):
    return repository.classify_brief_source(
        brief_source_id, payload.copy_type_id, {"confirmed": payload.confirmed}
    )


@router.post("/api/copy-types/{copy_type_id}/references", status_code=201)
def add_reference(
    copy_type_id: str, payload: ReferenceCreate, repository: Repository = Depends(get_repository)
):
    repository.get_copy_type(copy_type_id)
    return repository.add_reference(
        copy_type_id, payload.raw_text, payload.title, payload.body, payload.topics
    )


@router.get("/api/copy-types/{copy_type_id}/references")
def list_references(copy_type_id: str, repository: Repository = Depends(get_repository)):
    return repository.list_references(copy_type_id)


@router.post("/api/copy-types/{copy_type_id}/references:analyze")
async def analyze_references(
    copy_type_id: str,
    payload: ReferenceAnalyze | None = None,
    repository: Repository = Depends(get_repository),
    model_adapter=Depends(get_model_adapter),
):
    repository.get_copy_type(copy_type_id)
    if payload and payload.examples:
        repository.connection.execute(
            "DELETE FROM reference_examples WHERE copy_type_id=?", (copy_type_id,)
        )
        repository.connection.commit()
        for example in payload.examples:
            repository.add_reference(
                copy_type_id,
                example.raw_text,
                example.title,
                example.body,
                example.topics,
            )
    references = repository.list_references(copy_type_id)
    if not references:
        raise DomainError("REFERENCE_REQUIRED", "At least one reference example is required")
    context = ReferenceExamplesContext(
        examples=[
            ReferenceExample(
                raw_text=row["raw_text"],
                title=row["title"],
                body=row["body"],
                topics=json.loads(row["topics_json"]),
            )
            for row in references
        ]
    )
    profile = await model_adapter.analyze_reference_examples(context)
    repository.update_copy_type(
        copy_type_id,
        {"style_profile_json": profile.model_dump(mode="json"), "style_profile_confirmed": 0},
    )
    internal = profile.model_dump(mode="json")
    return {
        "title_hook": internal["hook_pattern"],
        "structure_rhythm": internal["structure"],
        "point_of_view": internal["narrative_perspective"],
        "tone": internal["tone"],
        "persona": internal["persona"],
        "scenario": internal["scenes"],
        "information_density": internal["information_density"],
        "ending": internal["ending_strategy"],
        "topic_strategy": internal["tag_strategy"],
        "source_facts": internal["source_facts_to_exclude"],
        "avoid_expressions": internal["expressions_to_avoid"],
        "confirmed": False,
    }
