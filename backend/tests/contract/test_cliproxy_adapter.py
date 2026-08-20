from __future__ import annotations

import json

import httpx
import pytest

from backend.app.domain.enums import BriefScope
from backend.app.domain.errors import DomainError
from backend.app.domain.schemas import (
    GenerationContext,
    ReferenceExample,
    ReferenceStyleProfile,
)
from backend.app.model.cliproxy import CliProxyModelAdapter


def adapter(
    client: httpx.AsyncClient,
    *,
    retry_limit: int = 0,
    api_mode: str = "responses",
) -> CliProxyModelAdapter:
    return CliProxyModelAdapter(
        base_url="https://cliproxy.test/v1",
        api_key="secret-key",
        generation_model="generation-model",
        qc_model="qc-model",
        reasoning_effort="medium",
        api_mode=api_mode,
        retry_limit=retry_limit,
        client=client,
    )


def generation_context() -> GenerationContext:
    return GenerationContext(
        project_facts={"brand": "当前品牌", "sku": "青柠味"},
        reference_examples=[
            ReferenceExample(
                raw_text="必须完整保留并传入的爆款原帖。来源品牌 9.9元。独特原句。",
                title="爆款标题",
                body="来源品牌 9.9元。独特原句。",
                topics=["#参考"],
            )
        ],
        style_profile=ReferenceStyleProfile(
            hook_pattern="具体痛点开头",
            opening_style="第一人称场景",
            structure="场景—事实—收尾",
            narrative_perspective="第一人称",
            tone="轻松克制",
            persona="通勤上班族",
            scenes="地铁与办公室",
            information_density="中等",
            selling_point_order="体验后事实",
            ending_strategy="自然收尾",
            tag_strategy="场景标签",
            source_facts_to_exclude=["来源品牌 9.9元"],
            expressions_to_avoid=["独特原句"],
        ),
        description_requirements=["轻松自然"],
        must_include=["通勤"],
        must_avoid=["绝对化"],
        effective_rules=["只用项目事实"],
        slot_id="slot-1",
        idempotency_key="idem-1",
    )


@pytest.mark.asyncio
async def test_responses_is_primary_and_contains_full_reference_prompt() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {"title": "生成标题", "body": "生成正文", "tags": ["#标签"]},
                    ensure_ascii=False,
                )
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await adapter(client).generate_copy(generation_context())

    request = captured["request"]
    assert isinstance(request, httpx.Request)
    assert request.url.path == "/v1/responses"
    assert request.headers["authorization"] == "Bearer secret-key"
    assert request.headers["idempotency-key"] == "idem-1"
    body = json.loads(request.content)
    assert body["model"] == "generation-model"
    assert body["reasoning"] == {"effort": "medium"}
    assert body["max_output_tokens"] == 4096
    prompt = body["input"]
    assert "必须完整保留并传入的爆款原帖" in prompt
    assert "当前品牌" in prompt
    assert "具体痛点开头" in prompt
    assert "来源品牌 9.9元" in prompt
    assert "独特原句" in prompt
    assert "来源事实" in body["instructions"]
    assert result.title == "生成标题"


@pytest.mark.asyncio
@pytest.mark.parametrize("response_shape", ["top", "nested"])
async def test_responses_supports_both_output_shapes(response_shape: str) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        payload = {
            "scope": "project",
            "sections": {
                "project_content": [],
                "copy_requirements": [],
                "project_qc": [],
                "conflicts": [],
            },
            "source_name": None,
        }
        text = json.dumps(payload)
        if response_shape == "top":
            return httpx.Response(200, json={"output_text": text})
        return httpx.Response(
            200,
            json={"output": [{"content": [{"type": "output_text", "text": text}]}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await adapter(client).parse_brief("原始 Brief", BriefScope.PROJECT)

    assert paths == ["/v1/responses"]
    assert result.scope == BriefScope.PROJECT


@pytest.mark.asyncio
async def test_chat_completions_is_only_an_unsupported_responses_fallback() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/responses"):
            return httpx.Response(404, json={"error": "unsupported"})
        payload = {
            "scope": "project",
            "sections": {
                "project_content": [],
                "copy_requirements": [],
                "project_qc": [],
                "conflicts": [],
            },
            "source_name": None,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await adapter(client, api_mode="auto").parse_brief(
            "原始 Brief", BriefScope.PROJECT
        )

    assert paths == ["/v1/responses", "/v1/chat/completions"]
    assert result.scope == BriefScope.PROJECT


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
async def test_auto_mode_does_not_hide_responses_request_errors(status: int) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(status, json={"error": "invalid request"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DomainError) as error:
            await adapter(client, api_mode="auto").parse_brief("Brief", BriefScope.PROJECT)

    assert error.value.code == "MODEL_RESPONSE_INVALID"
    assert paths == ["/v1/responses"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "MODEL_AUTH_FAILED"),
        (403, "MODEL_AUTH_FAILED"),
        (429, "MODEL_RATE_LIMITED"),
        (500, "MODEL_UNAVAILABLE"),
    ],
)
async def test_http_errors_are_sanitized(status: int, expected: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="secret-key vendor-private-body")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DomainError) as error:
            await adapter(client).parse_brief("Brief", BriefScope.PROJECT)

    assert error.value.code == expected
    assert "secret-key" not in str(error.value)
    assert "vendor-private-body" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}),
        httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]}),
    ],
)
async def test_invalid_provider_or_business_json_maps_to_one_code(
    response: httpx.Response,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DomainError) as error:
            await adapter(client).parse_brief("Brief", BriefScope.PROJECT)

    assert error.value.code == "MODEL_RESPONSE_INVALID"


@pytest.mark.asyncio
async def test_timeout_maps_without_leaking_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("contains-sensitive-request-data", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DomainError) as error:
            await adapter(client).parse_brief("Brief", BriefScope.PROJECT)

    assert error.value.code == "MODEL_TIMEOUT"
    assert "sensitive" not in str(error.value)


@pytest.mark.asyncio
async def test_copy_type_parse_prompt_requires_semantic_fields_and_project_suggestions() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        payload = {
            "scope": "copy_type",
            "sections": {
                "project_content": [],
                "copy_requirements": [],
                "project_qc": [],
                "conflicts": [],
            },
            "source_name": None,
            "copy_type_fields": {
                "title_direction": "通勤反差",
                "body_structure": "场景到体验",
                "tone": "轻松自然",
                "persona": "上班族",
                "scenario": "通勤",
                "topic_requirements": "品类与场景",
                "must_include": ["通勤"],
                "must_avoid": ["治愈"],
            },
            "project_change_suggestions": [
                {
                    "value": "清爽实验室",
                    "source_quote": "品牌：清爽实验室",
                    "confidence": 0.95,
                    "section": "brand",
                }
            ],
        }
        return httpx.Response(200, json={"output_text": json.dumps(payload, ensure_ascii=False)})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await adapter(client).parse_brief("语气：轻松自然", BriefScope.COPY_TYPE)

    body = captured["body"]
    assert isinstance(body, dict)
    assert "title_direction" in body["instructions"]
    assert "project_change_suggestions" in body["instructions"]
    assert result.copy_type_fields is not None
    assert result.copy_type_fields.tone == "轻松自然"
