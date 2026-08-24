from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..domain.enums import BriefScope
from ..domain.errors import DomainError
from ..domain.schemas import (
    AssistantAction,
    AssistantPlan,
    BriefFinding,
    BriefParseResult,
    BriefSections,
    CopyDraft,
    CopyTypeBriefFields,
    GenerationContext,
    ModelQcFinding,
    ReferenceExamplesContext,
    ReferenceStyleProfile,
    RewriteContext,
    SelectionRewriteContext,
    SemanticQcContext,
    SemanticQcResult,
)


def _stable_number(value: Any, upper: int = 10_000) -> int:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12], 16) % upper


def _text(value: Any) -> str:
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    return str(value)


def _fail_if_marked(value: Any) -> None:
    if "[MODEL_ERROR]" in _text(value):
        raise DomainError("MODEL_UNAVAILABLE", "Fake model unavailable", status_code=503)


def _flatten_fact_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _flatten_fact_values(nested)]
    if isinstance(value, (list, tuple)):
        return [item for nested in value for item in _flatten_fact_values(nested)]
    return []


class FakeModelAdapter:
    adapter_name = "fake"

    async def plan_project_setup(
        self,
        project: dict[str, object],
        history: list[dict[str, str]],
        user_message: str,
    ) -> AssistantPlan:
        _fail_if_marked(user_message)
        quantity_match = re.search(r"(?:生成|写|做)\s*(\d{1,3})\s*篇", user_message)
        quantity = int(quantity_match.group(1)) if quantity_match else None
        actions: list[AssistantAction] = []
        if quantity:
            actions.append(
                AssistantAction(
                    client_action_id="assistant-copy-type",
                    kind="upsert_copy_type",
                    payload={"name": "默认帖子类型", "quantity": quantity},
                )
            )
        if user_message.strip():
            actions.append(
                AssistantAction(
                    client_action_id="assistant-project",
                    kind="set_project",
                    payload={"name": str(project.get("name") or "新种草任务")},
                )
            )
        blockers = [] if quantity else ["请告诉我希望生成多少篇文案。"]
        return AssistantPlan(
            summary=f"我会按你的描述整理任务{f'，先准备 {quantity} 篇文案' if quantity else ''}。",
            blockers=blockers,
            assumptions=["未明确的产品事实会在生成前继续向你确认。"],
            actions=actions,
        )

    async def parse_brief(
        self,
        text: str,
        scope: BriefScope | str,
        source_name: str | None = None,
    ) -> BriefParseResult:
        _fail_if_marked(text)
        resolved_scope = BriefScope(scope)
        confidence = 0.45 if "[LOW_CONFIDENCE]" in text else 0.92
        lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
        if resolved_scope == BriefScope.COPY_TYPE:
            return self._parse_copy_type_brief(lines, confidence, source_name)
        return self._parse_project_brief(lines, confidence, source_name)

    @staticmethod
    def _parse_project_brief(
        lines: list[str], confidence: float, source_name: str | None
    ) -> BriefParseResult:
        project_aliases = {
            "项目名称": "project_name",
            "快消品类": "category",
            "品类": "category",
            "品牌": "brand",
            "产品": "product",
            "sku": "sku",
            "目标人群": "target_audience",
            "消费痛点": "pain_point",
            "典型使用场景": "scenario",
            "使用场景": "scenario",
            "核心卖点": "selling_point",
            "成分": "ingredients",
            "规格": "specification",
            "口味": "flavor",
            "价格": "price",
            "活动信息": "promotion",
            "活动": "promotion",
        }
        copy_aliases = {
            "语气": "tone",
            "调性": "tone",
            "品牌表达要求": "brand_expression",
            "文案要求": "copy_requirement",
            "竞品提及边界": "competitor_boundary",
        }
        qc_aliases = {
            "禁止宣称": "claim",
            "禁用宣称": "claim",
            "项目qc": "project_qc",
            "qc要求": "project_qc",
            "审查要求": "project_qc",
        }
        sections = BriefSections()
        for line in lines:
            parts = re.split(r"[：:]", line, maxsplit=1)
            key = parts[0].strip()
            normalized_key = key.lower()
            value = parts[1].strip() if len(parts) == 2 else line.strip()
            target = project_aliases.get(normalized_key)
            bucket = sections.project_content
            if target is None:
                target = copy_aliases.get(normalized_key)
                bucket = sections.copy_requirements
            if target is None:
                qc_key = next(
                    (alias for alias in qc_aliases if normalized_key.startswith(alias)), None
                )
                if qc_key:
                    target = qc_aliases[qc_key]
                    bucket = sections.project_qc
                    value = line.strip()
            if target is None:
                target = "unclassified"
                bucket = sections.conflicts
            bucket.append(
                BriefFinding(
                    value=value,
                    source_quote=line,
                    confidence=confidence,
                    section=target,
                )
            )
        return BriefParseResult(
            scope=BriefScope.PROJECT,
            sections=sections,
            source_name=source_name,
        )

    @staticmethod
    def _parse_copy_type_brief(
        lines: list[str], confidence: float, source_name: str | None
    ) -> BriefParseResult:
        field_aliases = {
            "标题方向": "title_direction",
            "标题": "title_direction",
            "正文结构": "body_structure",
            "内容结构": "body_structure",
            "结构": "body_structure",
            "语气": "tone",
            "调性": "tone",
            "人设": "persona",
            "身份": "persona",
            "场景": "scenario",
            "使用场景": "scenario",
            "话题要求": "topic_requirements",
            "话题": "topic_requirements",
            "标签": "topic_requirements",
        }
        list_aliases = {
            "一定要有": "must_include",
            "必须包含": "must_include",
            "必含": "must_include",
            "一定不要有": "must_avoid",
            "一定不要": "must_avoid",
            "禁止": "must_avoid",
            "禁用": "must_avoid",
        }
        qc_aliases = {
            "禁止宣称": "claim",
            "禁用宣称": "claim",
            "类型qc": "type_qc",
            "qc要求": "type_qc",
            "审查要求": "type_qc",
        }
        project_aliases = {
            "项目名称": "project_name",
            "品类": "category",
            "品牌": "brand",
            "产品": "product",
            "sku": "sku",
            "成分": "ingredients",
            "规格": "specification",
            "口味": "flavor",
            "价格": "price",
            "活动": "promotion",
            "目标人群": "target_audience",
            "消费痛点": "pain_point",
        }
        scalar_values = {field: "" for field in field_aliases.values()}
        list_values: dict[str, list[str]] = {"must_include": [], "must_avoid": []}
        requirements: list[BriefFinding] = []
        project_suggestions: list[BriefFinding] = []
        qc_proposals: list[BriefFinding] = []
        conflicts: list[BriefFinding] = []
        for line in lines:
            parts = re.split(r"[：:]", line, maxsplit=1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) == 2 else line.strip()
            normalized_key = key.lower()
            if normalized_key in project_aliases:
                project_suggestions.append(
                    BriefFinding(
                        value=value,
                        source_quote=line,
                        confidence=confidence,
                        section=project_aliases[normalized_key],
                    )
                )
            elif key in field_aliases:
                target = field_aliases[key]
                scalar_values[target] = "\n".join(filter(None, (scalar_values[target], value)))
                requirements.append(
                    BriefFinding(
                        value=value,
                        source_quote=line,
                        confidence=confidence,
                        section=target,
                    )
                )
            elif key in list_aliases:
                target = list_aliases[key]
                list_values[target].extend(
                    part.strip() for part in re.split(r"[、,，；;]", value) if part.strip()
                )
                requirements.append(
                    BriefFinding(
                        value=value,
                        source_quote=line,
                        confidence=confidence,
                        section=target,
                    )
                )
            elif qc_key := next(
                (alias for alias in qc_aliases if normalized_key.startswith(alias)), None
            ):
                qc_proposals.append(
                    BriefFinding(
                        value=line.strip(),
                        source_quote=line,
                        confidence=confidence,
                        section=qc_aliases[qc_key],
                    )
                )
            else:
                conflicts.append(
                    BriefFinding(
                        value=value,
                        source_quote=line,
                        confidence=confidence,
                        section="unclassified_requirement",
                    )
                )
        fields = CopyTypeBriefFields(**scalar_values, **list_values)
        return BriefParseResult(
            scope=BriefScope.COPY_TYPE,
            sections=BriefSections(
                project_content=project_suggestions,
                copy_requirements=requirements,
                project_qc=qc_proposals,
                conflicts=conflicts,
            ),
            source_name=source_name,
            copy_type_fields=fields,
            project_change_suggestions=project_suggestions,
        )

    async def analyze_reference_examples(
        self,
        context: ReferenceExamplesContext,
    ) -> ReferenceStyleProfile:
        _fail_if_marked(context)
        joined = "\n".join(example.raw_text for example in context.examples)
        source_facts = [
            segment.strip() for segment in re.split(r"[。！？；\n]+", joined) if segment.strip()
        ]
        if not source_facts:
            source_facts = ["参考案例中的品牌、价格、规格和功效事实"]
        seed = _stable_number([example.raw_text for example in context.examples])
        return ReferenceStyleProfile(
            hook_pattern="从具体生活困扰切入",
            opening_style="第一人称场景开场",
            structure="痛点—体验—事实—适用场景—自然收尾",
            narrative_perspective="第一人称真实体验",
            tone="轻松自然、克制",
            persona=f"生活方式分享者-{seed % 7 + 1}",
            scenes="用可感知的日常细节承载卖点",
            information_density="中等，每段一个信息点",
            selling_point_order="先体验后产品事实",
            ending_strategy="以使用建议或场景总结收尾",
            tag_strategy="产品品类与场景标签组合",
            source_facts_to_exclude=source_facts,
            expressions_to_avoid=["参考案例中的独特原句与连续表达"],
        )

    async def generate_copy(self, context: GenerationContext) -> CopyDraft:
        _fail_if_marked(context)
        seed = _stable_number(context.model_dump(mode="json"))
        facts = [
            fact for value in context.project_facts.values() for fact in _flatten_fact_values(value)
        ]
        lead = next((fact for fact in facts if len(fact) <= 16), None)
        lead = lead or (facts[0][:16] if facts else "这款产品")
        must = "、".join(context.must_include)
        title = f"{lead}，最近的日常小发现 {seed % 97 + 1}"[:40].rstrip()
        body_parts = [f"围绕{lead}整理一份日常场景参考。"]
        if len(facts) > 1:
            body_parts.append(f"产品信息以项目 Brief 为准：{'；'.join(facts[1:4])}。")
        if must:
            body_parts.append(f"这次特别关注：{must}。")
        body_parts.append("适不适合还是要看自己的需求和使用场景，理性参考就好。")
        return CopyDraft(title=title, body="\n".join(body_parts), tags=["#种草", "#日常分享"])

    async def run_semantic_qc(self, context: SemanticQcContext) -> SemanticQcResult:
        _fail_if_marked(context)
        content = f"{context.draft.title}\n{context.draft.body}"
        findings: list[ModelQcFinding] = []
        if "[FAIL_QC]" in content:
            findings.append(
                ModelQcFinding(
                    code="FAKE_QC_FAILURE",
                    message="测试标记触发语义 QC 问题",
                    severity="warning",
                    evidence="[FAIL_QC]",
                    suggestion="移除测试标记",
                    auto_fixable=True,
                )
            )
        confidence = 0.45 if "[LOW_CONFIDENCE]" in content else 0.94
        return SemanticQcResult(findings=findings, confidence=confidence)

    async def rewrite_copy(self, context: RewriteContext) -> CopyDraft:
        _fail_if_marked(context)
        title = context.draft.title.replace("[FAIL_QC]", "").strip()
        if len(title) > 40 or any(
            finding.code.lower() in {"length", "title_length"}
            or "title length" in finding.message.lower()
            for finding in context.findings
        ):
            title = title[:40].rstrip()
        body = context.draft.body.replace("[FAIL_QC]", "").strip()
        if context.findings:
            body = f"{body}\n（已按指定问题修订）"
        return CopyDraft(title=title, body=body, tags=list(context.draft.tags))

    async def rewrite_selection(self, context: SelectionRewriteContext) -> str:
        _fail_if_marked(context)
        selected = context.selected_text.replace("[FAIL_QC]", "").strip()
        return f"{selected}（{context.direction.strip()}）"
