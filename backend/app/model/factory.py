from __future__ import annotations

import httpx

from ..config import Settings
from ..domain.errors import DomainError
from .cliproxy import CliProxyModelAdapter
from .fake import FakeModelAdapter
from .protocol import ModelAdapter


def build_model_adapter(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> ModelAdapter:
    adapter = settings.model_adapter.strip().lower()
    if adapter == "fake":
        return FakeModelAdapter()
    if adapter == "cliproxy":
        required = {
            "CLIPROXY_BASE_URL": settings.cliproxy_base_url,
            "CLIPROXY_API_KEY": settings.cliproxy_api_key,
            "CLIPROXY_GENERATION_MODEL": settings.cliproxy_generation_model,
            "CLIPROXY_QC_MODEL": settings.cliproxy_qc_model,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise DomainError(
                "MODEL_NOT_CONFIGURED",
                "CLIPROXY configuration is incomplete",
                details={"missing": missing},
                status_code=503,
            )
        return CliProxyModelAdapter(
            base_url=settings.cliproxy_base_url,
            api_key=settings.cliproxy_api_key,
            generation_model=settings.cliproxy_generation_model,
            qc_model=settings.cliproxy_qc_model,
            reasoning_effort=settings.cliproxy_reasoning_effort,
            api_mode=settings.cliproxy_api_mode,
            timeout_seconds=settings.cliproxy_timeout_seconds,
            retry_limit=settings.api_retry_limit,
            client=client,
        )
    raise DomainError(
        "MODEL_ADAPTER_UNSUPPORTED",
        "Unsupported model adapter",
        details={"adapter": adapter},
        status_code=500,
    )
