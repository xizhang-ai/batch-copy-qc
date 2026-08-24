from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import BriefScope


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssistantAction(StrictModel):
    client_action_id: str = Field(min_length=1, max_length=100)
    kind: Literal[
        "set_project",
        "replace_project_findings",
        "upsert_copy_type",
        "replace_project_rules",
        "start_generation",
    ]
    payload: dict[str, Any]


class AssistantPlan(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    blockers: list[str] = Field(default_factory=list, max_length=3)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    actions: list[AssistantAction] = Field(default_factory=list, max_length=20)


class AssistantMessageCreate(StrictModel):
    content: str = Field(min_length=1, max_length=12000)


class PreviewConfirmation(StrictModel):
    expected_preview_item_count: int = Field(ge=1, le=3)


class BriefFinding(StrictModel):
    value: str
    source_quote: str
    confidence: float = Field(ge=0, le=1)
    section: str


class BriefSections(StrictModel):
    project_content: list[BriefFinding] = Field(default_factory=list)
    copy_requirements: list[BriefFinding] = Field(default_factory=list)
    project_qc: list[BriefFinding] = Field(default_factory=list)
    conflicts: list[BriefFinding] = Field(default_factory=list)


class CopyTypeBriefFields(StrictModel):
    title_direction: str = ""
    body_structure: str = ""
    tone: str = ""
    persona: str = ""
    scenario: str = ""
    topic_requirements: str = ""
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)


class BriefParseResult(StrictModel):
    scope: BriefScope
    sections: BriefSections
    source_name: str | None = None
    copy_type_fields: CopyTypeBriefFields | None = None
    project_change_suggestions: list[BriefFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_copy_type_fields_for_copy_type_scope(self):
        if self.scope == BriefScope.COPY_TYPE and self.copy_type_fields is None:
            raise ValueError("copy_type_fields are required for copy_type scope")
        return self


class ReferenceExample(StrictModel):
    raw_text: str
    title: str = ""
    body: str = ""
    topics: list[str] = Field(default_factory=list)


class ReferenceExamplesContext(StrictModel):
    examples: list[ReferenceExample] = Field(min_length=1, max_length=5)


class ReferenceStyleProfile(StrictModel):
    hook_pattern: str = ""
    opening_style: str = ""
    structure: str = ""
    narrative_perspective: str = ""
    tone: str = ""
    persona: str = ""
    scenes: str = ""
    information_density: str = ""
    selling_point_order: str = ""
    ending_strategy: str = ""
    tag_strategy: str = ""
    source_facts_to_exclude: list[str] = Field(default_factory=list)
    expressions_to_avoid: list[str] = Field(default_factory=list)


class GenerationContext(StrictModel):
    project_facts: dict[str, Any]
    reference_examples: list[ReferenceExample] = Field(default_factory=list, max_length=5)
    style_profile: ReferenceStyleProfile | None = None
    description_requirements: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    effective_rules: list[str] = Field(default_factory=list)
    slot_id: str
    idempotency_key: str


class CopyDraft(StrictModel):
    title: str
    body: str
    tags: list[str]


class ModelQcFinding(StrictModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    rule_id: str | None = None
    rule_index: int | None = Field(default=None, ge=0)
    violated_rule: str | None = None
    evidence: str | None = None
    suggestion: str | None = None
    auto_fixable: bool = False


class SemanticQcRule(StrictModel):
    id: str
    level: Literal["hard", "soft"]
    category: str
    requirement: str


class SemanticQcContext(StrictModel):
    draft: CopyDraft
    project_facts: dict[str, Any]
    rules: list[SemanticQcRule]
    similarity_context: list[str] = Field(default_factory=list)


class SemanticQcResult(StrictModel):
    findings: list[ModelQcFinding] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class RewriteContext(StrictModel):
    draft: CopyDraft
    findings: list[ModelQcFinding]
    hard_rules: list[str]


class SelectionRewriteContext(StrictModel):
    field: Literal["title", "body"]
    selected_text: str
    context: str
    direction: str
