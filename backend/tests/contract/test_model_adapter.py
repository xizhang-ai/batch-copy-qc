from __future__ import annotations

import pytest

from backend.app.domain.enums import BriefScope
from backend.app.domain.errors import DomainError
from backend.app.domain.schemas import (
    CopyDraft,
    GenerationContext,
    ModelQcFinding,
    ReferenceExample,
    ReferenceExamplesContext,
    RewriteContext,
    SelectionRewriteContext,
    SemanticQcContext,
    SemanticQcRule,
)
from backend.app.model.fake import FakeModelAdapter


def reference_context() -> ReferenceExamplesContext:
    return ReferenceExamplesContext(
        examples=[
            ReferenceExample(
                raw_text="原帖完整内容：虚构汽水 19.9元，喝完立刻变瘦。",
                title="虚构标题",
                body="虚构汽水 19.9元，喝完立刻变瘦。",
                topics=["#虚构"],
            )
        ]
    )


def generation_context() -> GenerationContext:
    return GenerationContext(
        project_facts={"brand": "当前品牌", "product": "青柠气泡水"},
        reference_examples=reference_context().examples,
        style_profile=None,
        description_requirements=["轻松自然"],
        must_include=["通勤场景"],
        must_avoid=["立刻见效"],
        effective_rules=["不得虚构价格"],
        slot_id="slot-1",
        idempotency_key="idem-1",
    )


@pytest.mark.asyncio
async def test_fake_adapter_six_operations_return_contract_types() -> None:
    adapter = FakeModelAdapter()
    parsed = await adapter.parse_brief(
        "项目名称：夏日气泡水\n目标人群：通勤族", BriefScope.PROJECT, "brief.txt"
    )
    profile = await adapter.analyze_reference_examples(reference_context())
    draft = await adapter.generate_copy(generation_context())
    qc = await adapter.run_semantic_qc(
        SemanticQcContext(
            draft=draft,
            project_facts={"brand": "当前品牌"},
            rules=[
                SemanticQcRule(
                    id="rule-1",
                    level="hard",
                    category="claim",
                    requirement="不得虚构",
                )
            ],
        )
    )
    rewritten = await adapter.rewrite_copy(
        RewriteContext(
            draft=CopyDraft(title="[FAIL_QC] 标题", body="正文", tags=["#标签"]),
            findings=[ModelQcFinding(code="X", message="移除标记")],
            hard_rules=["不得虚构"],
        )
    )
    selection = await adapter.rewrite_selection(
        SelectionRewriteContext(
            field="body",
            selected_text="有点好喝",
            context="完整上下文",
            direction="更具体",
        )
    )

    assert parsed.sections.project_content
    assert parsed.sections.project_content[0].source_quote == "项目名称：夏日气泡水"
    assert profile.hook_pattern and profile.structure
    assert any("19.9元" in fact for fact in profile.source_facts_to_exclude)
    assert any("虚构汽水" in fact for fact in profile.source_facts_to_exclude)
    assert any("立刻变瘦" in fact for fact in profile.source_facts_to_exclude)
    assert draft.title and draft.body and draft.tags
    assert "虚构汽水" not in draft.body
    assert "19.9元" not in draft.body
    assert "立刻变瘦" not in draft.body
    assert "试了" not in draft.body and "真实感受" not in draft.body
    assert qc.findings == []
    assert "[FAIL_QC]" not in rewritten.title
    assert selection == "有点好喝（更具体）"


@pytest.mark.asyncio
async def test_fake_is_deterministic_and_supports_markers() -> None:
    adapter = FakeModelAdapter()
    first = await adapter.generate_copy(generation_context())
    second = await adapter.generate_copy(generation_context())
    low = await adapter.run_semantic_qc(
        SemanticQcContext(
            draft=CopyDraft(title="[LOW_CONFIDENCE]", body="[FAIL_QC]", tags=[]),
            project_facts={},
            rules=[],
        )
    )

    assert first == second
    assert low.confidence < 0.7
    assert low.findings[0].code == "FAKE_QC_FAILURE"

    with pytest.raises(DomainError) as error:
        await adapter.parse_brief("[MODEL_ERROR]", BriefScope.PROJECT)
    assert error.value.code == "MODEL_UNAVAILABLE"


@pytest.mark.asyncio
async def test_fake_copy_type_brief_has_stable_semantic_fields_and_fact_suggestions() -> None:
    parsed = await FakeModelAdapter().parse_brief(
        "语气：轻松自然\n标题方向：通勤反差\n一定要有：通勤\n品牌：清爽实验室",
        BriefScope.COPY_TYPE,
    )

    assert parsed.copy_type_fields is not None
    assert parsed.copy_type_fields.tone == "轻松自然"
    assert parsed.copy_type_fields.title_direction == "通勤反差"
    assert parsed.copy_type_fields.must_include == ["通勤"]
    assert parsed.project_change_suggestions[0].section == "brand"


@pytest.mark.asyncio
async def test_fake_generation_flattens_list_facts_and_caps_title_length() -> None:
    context = generation_context().model_copy(
        update={
            "project_facts": {
                "产品": ["清爽气泡水", "青柠味"],
                "卖点": ["零糖", ["低热量"]],
            }
        }
    )

    draft = await FakeModelAdapter().generate_copy(context)

    assert len(draft.title) <= 40
    assert "['" not in draft.title
    assert "清爽气泡水" in draft.title


@pytest.mark.asyncio
async def test_fake_rewrite_shortens_title_for_length_finding() -> None:
    rewritten = await FakeModelAdapter().rewrite_copy(
        RewriteContext(
            draft=CopyDraft(title="很长的标题" * 20, body="正文", tags=["#标签"]),
            findings=[
                ModelQcFinding(
                    code="length",
                    message="Title length must be 1-40",
                    auto_fixable=True,
                )
            ],
            hard_rules=[],
        )
    )

    assert len(rewritten.title) <= 40
