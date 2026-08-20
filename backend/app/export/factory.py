from __future__ import annotations

import httpx

from ..config import Settings
from ..domain.errors import DomainError
from .fake import FakeFeishuExporter
from .feishu import FeishuApiExporter
from .protocol import FeishuExporter


def build_exporter(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> FeishuExporter:
    adapter = settings.feishu_adapter.strip().lower()
    if adapter == "fake":
        return FakeFeishuExporter()
    if adapter == "feishu":
        wiki_node_token = getattr(settings, "feishu_wiki_node_token", "")
        return FeishuApiExporter(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            spreadsheet_token=settings.feishu_spreadsheet_token,
            wiki_node_token=wiki_node_token,
            base_url=settings.feishu_base_url,
            timeout_seconds=settings.cliproxy_timeout_seconds,
            client=client,
        )
    if adapter == "unconfigured":
        raise DomainError(
            "FEISHU_NOT_CONFIGURED",
            "Feishu export is not configured",
            status_code=503,
        )
    raise DomainError(
        "FEISHU_ADAPTER_UNSUPPORTED",
        "Unsupported Feishu adapter",
        details={"adapter": adapter},
        status_code=500,
    )
