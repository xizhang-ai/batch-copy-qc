from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.enums import BriefScope
from ..domain.schemas import (
    AssistantPlan,
    BriefParseResult,
    CopyDraft,
    GenerationContext,
    ReferenceExamplesContext,
    ReferenceStyleProfile,
    RewriteContext,
    SelectionRewriteContext,
    SemanticQcContext,
    SemanticQcResult,
)


@runtime_checkable
class ModelAdapter(Protocol):
    async def plan_project_setup(
        self,
        project: dict[str, object],
        history: list[dict[str, str]],
        user_message: str,
    ) -> AssistantPlan: ...

    async def parse_brief(
        self,
        text: str,
        scope: BriefScope | str,
        source_name: str | None = None,
    ) -> BriefParseResult: ...

    async def analyze_reference_examples(
        self,
        context: ReferenceExamplesContext,
    ) -> ReferenceStyleProfile: ...

    async def generate_copy(self, context: GenerationContext) -> CopyDraft: ...

    async def run_semantic_qc(self, context: SemanticQcContext) -> SemanticQcResult: ...

    async def rewrite_copy(self, context: RewriteContext) -> CopyDraft: ...

    async def rewrite_selection(self, context: SelectionRewriteContext) -> str: ...
