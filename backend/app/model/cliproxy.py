from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from ..domain.enums import BriefScope
from ..domain.errors import DomainError
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

LOGGER = logging.getLogger(__name__)
ResultT = TypeVar("ResultT", bound=BaseModel)


class _EndpointUnsupported(Exception):
    pass


class _SelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    replacement: str


INSTRUCTIONS: dict[str, str] = {
    "plan_project_setup": (
        "你是种草文案任务助手。把用户的表达转为可审阅、可执行的任务建议，"
        "不得直接声称已保存或已生成。只使用 actions 白名单中的 kind，"
        "每个动作都必须有稳定、非空的 client_action_id。只有影响生成安全的缺失信息"
        "才能放 blockers，最多三个；非关键推断放 assumptions。返回严格 JSON。"
    ),
    "parse_brief": (
        "你是 Brief 信息抽取器。只抽取输入原文明确存在的信息，不推测、不补充事实。"
        "每个 finding 都必须逐字给出 source_quote、0到1置信度和 section。"
        "当 scope=project 时，产品/品牌/SKU/卖点/成分/规格等事实放 project_content，"
        "语气/调性/表达要求放 copy_requirements，禁止宣称/审核边界放 project_qc，"
        "无法可靠分类的内容才放 conflicts。section 必须是稳定语义键而不是分组名称。"
        "当 scope=copy_type 时，copy_type_fields 必须始终返回固定字段："
        "title_direction、body_structure、tone、persona、scenario、topic_requirements、"
        "must_include、must_avoid；原文未提供的字符串留空、列表留空，不得把未知要求塞入"
        "body_structure。类型 Brief 中出现的品牌、产品、SKU、成分、规格、口味、价格、活动、"
        "目标人群等项目级事实必须只放入 project_change_suggestions，并保留原文依据，"
        "不得写入 copy_type_fields，也不得视为已确认项目事实。"
        "按要求返回严格 JSON，且不得出现 schema 外字段。"
    ),
    "analyze_reference_examples": (
        "你是小红书快消种草文案风格分析器。分析写作手法而不是复制内容。"
        "把参考帖品牌、价格、规格、功效等事实放入 source_facts_to_exclude；"
        "把独特句式或可能造成照搬的表达放入 expressions_to_avoid。不得建立当前项目事实。"
    ),
    "generate_copy": (
        "你是小红书快消类种草文案生成器。project_facts 是唯一事实来源。"
        "reference_examples 原帖全文只用于理解结构与风格，严禁使用其中的品牌、价格、规格、"
        "功效等来源事实，严禁照搬独特原句。必须遵守 must_include、must_avoid 和 effective_rules。"
        "输出自然、克制的标题、正文和标签 JSON，不作未经支持的宣称。"
    ),
    "run_semantic_qc": (
        "你是独立 QC 审查官。按项目事实和规则审查当前文案，并参考批次相似上下文。"
        "rules 中每条都有 id、level、category、requirement。每个规则违规必须原样返回 rule_id；"
        "若确实无法返回 rule_id，至少返回零基 rule_index 或逐字 violated_rule。"
        "severity=error 表示阻断问题，绝不能把 hard 规则违规降为 warning。"
        "只报告有证据的问题，不修改文案、不决定强制通过。返回严格 JSON。"
    ),
    "rewrite_copy": (
        "你是受约束的文案修改器。只修复指定 findings，严格遵守 hard_rules，"
        "不得新增项目事实。返回完整的新标题、正文和标签。"
    ),
    "rewrite_selection": (
        "你是局部文字修改器。只返回选中文字的替换片段，不返回整篇文案，"
        "不新增事实，并遵照人工 direction。"
    ),
}


class CliProxyModelAdapter:
    adapter_name = "cliproxy"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        generation_model: str,
        qc_model: str,
        reasoning_effort: str = "medium",
        api_mode: str = "responses",
        timeout_seconds: float = 120,
        retry_limit: int = 2,
        max_output_tokens: int = 4096,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url or not api_key or not generation_model or not qc_model:
            raise DomainError(
                "MODEL_NOT_CONFIGURED",
                "CLIPROXY configuration is incomplete",
                status_code=503,
            )
        normalized = base_url.rstrip("/")
        self._api_root = normalized if normalized.endswith("/v1") else f"{normalized}/v1"
        self._api_key = api_key
        self._generation_model = generation_model
        self._qc_model = qc_model
        self._reasoning_effort = reasoning_effort.strip()
        if api_mode not in {"responses", "auto", "chat"}:
            raise DomainError(
                "MODEL_PROTOCOL_INVALID",
                "Unsupported CLIPROXY API mode",
                status_code=500,
            )
        self._api_mode = api_mode
        self._timeout = timeout_seconds
        self._retry_limit = retry_limit
        self._max_output_tokens = max_output_tokens
        self._client = client

    async def parse_brief(
        self,
        text: str,
        scope: BriefScope | str,
        source_name: str | None = None,
    ) -> BriefParseResult:
        resolved_scope = BriefScope(scope)
        return await self._invoke(
            "parse_brief",
            {"text": text, "scope": resolved_scope.value, "source_name": source_name},
            BriefParseResult,
        )

    async def plan_project_setup(
        self,
        project: dict[str, object],
        history: list[dict[str, str]],
        user_message: str,
    ) -> AssistantPlan:
        return await self._invoke(
            "plan_project_setup",
            {"project": project, "history": history[-12:], "user_message": user_message},
            AssistantPlan,
        )

    async def analyze_reference_examples(
        self,
        context: ReferenceExamplesContext,
    ) -> ReferenceStyleProfile:
        return await self._invoke(
            "analyze_reference_examples",
            context.model_dump(mode="json"),
            ReferenceStyleProfile,
        )

    async def generate_copy(self, context: GenerationContext) -> CopyDraft:
        return await self._invoke(
            "generate_copy",
            context.model_dump(mode="json"),
            CopyDraft,
            idempotency_key=context.idempotency_key,
        )

    async def run_semantic_qc(self, context: SemanticQcContext) -> SemanticQcResult:
        return await self._invoke(
            "run_semantic_qc",
            context.model_dump(mode="json"),
            SemanticQcResult,
            model=self._qc_model,
        )

    async def rewrite_copy(self, context: RewriteContext) -> CopyDraft:
        return await self._invoke(
            "rewrite_copy",
            context.model_dump(mode="json"),
            CopyDraft,
        )

    async def rewrite_selection(self, context: SelectionRewriteContext) -> str:
        result = await self._invoke(
            "rewrite_selection",
            context.model_dump(mode="json"),
            _SelectionResult,
        )
        return result.replacement

    async def _invoke(
        self,
        operation: str,
        input_data: dict[str, Any],
        result_type: type[ResultT],
        *,
        model: str | None = None,
        idempotency_key: str | None = None,
    ) -> ResultT:
        selected_model = model or self._generation_model
        prompt = json.dumps(
            {
                "operation": operation,
                "input": input_data,
                "required_output_schema": result_type.model_json_schema(),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        started = time.monotonic()
        error_code: str | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None
        try:
            if self._api_mode == "chat":
                provider_data = await self._request_chat(
                    selected_model,
                    INSTRUCTIONS[operation],
                    prompt,
                    idempotency_key=idempotency_key,
                )
                output_text = self._chat_output_text(provider_data)
            else:
                try:
                    provider_data = await self._request_responses(
                        selected_model,
                        INSTRUCTIONS[operation],
                        prompt,
                        idempotency_key=idempotency_key,
                        allow_fallback=self._api_mode == "auto",
                    )
                    output_text = self._responses_output_text(provider_data)
                except _EndpointUnsupported:
                    provider_data = await self._request_chat(
                        selected_model,
                        INSTRUCTIONS[operation],
                        prompt,
                        idempotency_key=idempotency_key,
                    )
                    output_text = self._chat_output_text(provider_data)
            input_tokens, output_tokens = self._token_usage(provider_data)
            parsed = self._parse_json_output(output_text)
            return result_type.model_validate(parsed)
        except DomainError as exc:
            error_code = exc.code
            raise
        except (ValidationError, ValueError, TypeError, KeyError, IndexError) as exc:
            error_code = "MODEL_RESPONSE_INVALID"
            raise DomainError(
                "MODEL_RESPONSE_INVALID",
                "Model returned invalid structured data",
                status_code=502,
            ) from exc
        finally:
            LOGGER.info(
                "model_call operation=%s adapter=cliproxy model=%s "
                "duration_ms=%d status=%s input_tokens=%s output_tokens=%s error_code=%s",
                operation,
                selected_model,
                int((time.monotonic() - started) * 1000),
                "failed" if error_code else "succeeded",
                input_tokens if input_tokens is not None else "",
                output_tokens if output_tokens is not None else "",
                error_code or "",
            )

    async def _request_chat(
        self,
        model: str,
        instructions: str,
        prompt: str,
        *,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self._max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort
        return await self._request_json(
            "/chat/completions",
            body,
            idempotency_key=idempotency_key,
            allow_endpoint_fallback=False,
        )

    async def _request_responses(
        self,
        model: str,
        instructions: str,
        prompt: str,
        *,
        idempotency_key: str | None,
        allow_fallback: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": prompt,
            "max_output_tokens": self._max_output_tokens,
        }
        if self._reasoning_effort:
            body["reasoning"] = {"effort": self._reasoning_effort}
        return await self._request_json(
            "/responses",
            body,
            idempotency_key=idempotency_key,
            allow_endpoint_fallback=allow_fallback,
        )

    async def _request_json(
        self,
        path: str,
        body: dict[str, Any],
        *,
        idempotency_key: str | None,
        allow_endpoint_fallback: bool,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self._retry_limit + 1):
            try:
                if self._client is not None:
                    response = await self._client.post(
                        f"{self._api_root}{path}",
                        headers=headers,
                        json=body,
                        timeout=self._timeout,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.post(
                            f"{self._api_root}{path}",
                            headers=headers,
                            json=body,
                        )
            except httpx.TimeoutException as exc:
                if attempt < self._retry_limit:
                    continue
                raise DomainError(
                    "MODEL_TIMEOUT",
                    "Model request timed out",
                    status_code=504,
                ) from exc
            except httpx.HTTPError as exc:
                if attempt < self._retry_limit:
                    continue
                raise DomainError(
                    "MODEL_UNAVAILABLE",
                    "Model service is unavailable",
                    status_code=503,
                ) from exc

            if allow_endpoint_fallback and response.status_code in {404, 405, 501}:
                raise _EndpointUnsupported
            if response.status_code in {401, 403}:
                raise DomainError(
                    "MODEL_AUTH_FAILED",
                    "Model authentication failed",
                    status_code=401,
                )
            if response.status_code == 429:
                if attempt < self._retry_limit:
                    await self._respect_retry_after(response)
                    continue
                raise DomainError("MODEL_RATE_LIMITED", "Model rate limited", status_code=429)
            if response.status_code >= 500:
                if attempt < self._retry_limit:
                    continue
                raise DomainError(
                    "MODEL_UNAVAILABLE",
                    "Model service is unavailable",
                    status_code=503,
                )
            if response.is_error:
                raise DomainError(
                    "MODEL_RESPONSE_INVALID",
                    "Model request was rejected",
                    status_code=502,
                )
            try:
                data = response.json()
            except ValueError as exc:
                raise DomainError(
                    "MODEL_RESPONSE_INVALID",
                    "Model returned invalid data",
                    status_code=502,
                ) from exc
            if not isinstance(data, dict):
                raise DomainError(
                    "MODEL_RESPONSE_INVALID",
                    "Model returned invalid data",
                    status_code=502,
                )
            return data
        raise AssertionError("retry loop exhausted")

    @staticmethod
    def _chat_output_text(data: dict[str, Any]) -> str:
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "".join(text for text in parts if isinstance(text, str))
        raise TypeError("unsupported chat content")

    @staticmethod
    def _responses_output_text(data: dict[str, Any]) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        parts: list[str] = []
        for output in data.get("output", []):
            if not isinstance(output, dict):
                continue
            for content in output.get("content", []):
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    parts.append(content["text"])
        return "".join(parts)

    @staticmethod
    def _parse_json_output(output_text: str) -> Any:
        text = output_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        if not text:
            raise ValueError("empty output")
        return json.loads(text)

    @staticmethod
    def _token_usage(data: dict[str, Any]) -> tuple[int | None, int | None]:
        usage = data.get("usage")
        if not isinstance(usage, dict):
            return None, None
        input_value = usage.get("input_tokens", usage.get("prompt_tokens"))
        output_value = usage.get("output_tokens", usage.get("completion_tokens"))
        return (
            input_value if isinstance(input_value, int) else None,
            output_value if isinstance(output_value, int) else None,
        )

    @staticmethod
    async def _respect_retry_after(response: httpx.Response) -> None:
        raw_value = response.headers.get("Retry-After", "0")
        try:
            delay = float(raw_value)
        except ValueError:
            delay = 0
        await asyncio.sleep(max(0, min(delay, 60)))
