from __future__ import annotations

import time
from typing import Any

import httpx

from ..domain.errors import DomainError
from .protocol import EXPORT_HEADERS, CreateRunSheet, ExportRow, SheetRef

_AUTH_CODES = {99991663, 99991664, 99991665, 99991668, 99991669}
_PERMISSION_CODES = {99991672, 99991673}
_RATE_LIMIT_CODES = {99991400, 99991401, 99991402}


class FeishuApiExporter:
    """Minimal Feishu Sheets adapter with Wiki-token resolution.

    Credentials stay inside request headers/bodies. Raised errors expose only the
    project's stable error code, never Feishu's raw response body.
    """

    adapter_name = "feishu"

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        spreadsheet_token: str = "",
        wiki_node_token: str = "",
        base_url: str = "https://open.feishu.cn",
        timeout_seconds: float = 120,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not app_id or not app_secret or not (spreadsheet_token or wiki_node_token):
            raise DomainError(
                "FEISHU_NOT_CONFIGURED",
                "Feishu export is not configured",
                status_code=503,
            )
        self._app_id = app_id
        self._app_secret = app_secret
        self._spreadsheet_token = spreadsheet_token
        self._wiki_node_token = wiki_node_token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client
        self._tenant_token: str | None = None
        self._tenant_token_expires_at = 0.0

    async def find_run_sheet(self, request: CreateRunSheet) -> SheetRef | None:
        spreadsheet_token = await self._get_spreadsheet_token()
        data = await self._authorized_json(
            "GET",
            f"/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query",
            operation_code="FEISHU_SHEET_CREATE_FAILED",
        )
        sheets = data.get("data", {}).get("sheets", [])
        if not isinstance(sheets, list):
            return None
        for raw_sheet in sheets:
            if not isinstance(raw_sheet, dict):
                continue
            properties = raw_sheet.get("properties", {})
            title = raw_sheet.get("title") or (
                properties.get("title") if isinstance(properties, dict) else None
            )
            sheet_id = (
                raw_sheet.get("sheet_id")
                or raw_sheet.get("sheetId")
                or (properties.get("sheetId") if isinstance(properties, dict) else None)
            )
            if title == request.sheet_title and isinstance(sheet_id, str) and sheet_id:
                return SheetRef(
                    export_run_id=request.export_run_id,
                    sheet_id=sheet_id,
                    title=title,
                )
        return None

    async def create_run_sheet(self, request: CreateRunSheet) -> SheetRef:
        spreadsheet_token = await self._get_spreadsheet_token()
        payload = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": request.sheet_title,
                        }
                    }
                }
            ]
        }
        data = await self._authorized_json(
            "POST",
            f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/sheets_batch_update",
            operation_code="FEISHU_SHEET_CREATE_FAILED",
            json=payload,
        )
        try:
            sheet_id = data["data"]["replies"][0]["addSheet"]["properties"]["sheetId"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DomainError(
                "FEISHU_SHEET_CREATE_FAILED",
                "Feishu did not return a created sheet",
                status_code=502,
            ) from exc
        if not isinstance(sheet_id, str) or not sheet_id:
            raise DomainError(
                "FEISHU_SHEET_CREATE_FAILED",
                "Feishu did not return a created sheet",
                status_code=502,
            )
        return SheetRef(
            export_run_id=request.export_run_id,
            sheet_id=sheet_id,
            title=request.sheet_title,
        )

    async def write_rows(
        self,
        sheet: SheetRef,
        rows: list[ExportRow],
        *,
        clear_through_row: int = 0,
    ) -> None:
        spreadsheet_token = await self._get_spreadsheet_token()
        ordered = sorted(rows, key=lambda row: (row.ordinal, row.item_id))
        values: list[list[str | int]] = [list(EXPORT_HEADERS)]
        values.extend(row.to_values() for row in ordered)
        end_row = max(len(values), clear_through_row)
        values.extend([[""] * len(EXPORT_HEADERS) for _ in range(end_row - len(values))])
        await self._authorized_json(
            "PUT",
            f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values",
            operation_code="FEISHU_ROWS_WRITE_FAILED",
            json={
                "valueRange": {
                    "range": f"{sheet.sheet_id}!A1:I{end_row}",
                    "values": values,
                }
            },
        )

    async def _get_spreadsheet_token(self) -> str:
        if self._spreadsheet_token:
            return self._spreadsheet_token
        data = await self._authorized_json(
            "GET",
            "/open-apis/wiki/v2/spaces/get_node",
            operation_code="FEISHU_PERMISSION_DENIED",
            params={"token": self._wiki_node_token},
        )
        try:
            node = data["data"]["node"]
            obj_type = node["obj_type"]
            obj_token = node["obj_token"]
        except (KeyError, TypeError) as exc:
            raise DomainError(
                "FEISHU_PERMISSION_DENIED",
                "Unable to resolve the configured Feishu Wiki node",
                status_code=403,
            ) from exc
        if obj_type != "sheet" or not isinstance(obj_token, str) or not obj_token:
            raise DomainError(
                "FEISHU_PERMISSION_DENIED",
                "The configured Feishu Wiki node is not a spreadsheet",
                status_code=403,
            )
        self._spreadsheet_token = obj_token
        return obj_token

    async def _tenant_access_token(self, *, force_refresh: bool = False) -> str:
        if (
            not force_refresh
            and self._tenant_token
            and time.monotonic() < self._tenant_token_expires_at
        ):
            return self._tenant_token
        response = await self._request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self._app_id, "app_secret": self._app_secret},
            include_auth=False,
            operation_code="FEISHU_AUTH_FAILED",
        )
        try:
            token = response["tenant_access_token"]
        except (KeyError, TypeError) as exc:
            raise DomainError(
                "FEISHU_AUTH_FAILED",
                "Feishu authentication failed",
                status_code=401,
            ) from exc
        if not isinstance(token, str) or not token:
            raise DomainError(
                "FEISHU_AUTH_FAILED",
                "Feishu authentication failed",
                status_code=401,
            )
        self._tenant_token = token
        raw_expiry = response.get("expire", response.get("expire_in", 7200))
        expires_in = float(raw_expiry) if isinstance(raw_expiry, (int, float)) else 7200.0
        self._tenant_token_expires_at = time.monotonic() + max(0.0, expires_in - 60.0)
        return token

    async def _authorized_json(
        self,
        method: str,
        path: str,
        *,
        operation_code: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        for attempt in range(2):
            await self._tenant_access_token(force_refresh=attempt > 0)
            try:
                return await self._request(
                    method,
                    path,
                    include_auth=True,
                    operation_code=operation_code,
                    **kwargs,
                )
            except DomainError as exc:
                if attempt == 0 and exc.code == "FEISHU_AUTH_FAILED":
                    self._tenant_token = None
                    self._tenant_token_expires_at = 0.0
                    continue
                raise
        raise AssertionError("Feishu auth retry exhausted")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        include_auth: bool,
        operation_code: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if include_auth:
            headers["Authorization"] = f"Bearer {self._tenant_token}"
        try:
            if self._client is not None:
                response = await self._client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    timeout=self._timeout,
                    **kwargs,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(
                        method,
                        f"{self._base_url}{path}",
                        headers=headers,
                        **kwargs,
                    )
        except httpx.TimeoutException as exc:
            raise DomainError(
                operation_code,
                "Feishu request timed out",
                status_code=503,
            ) from exc
        except httpx.HTTPError as exc:
            raise DomainError(
                operation_code,
                "Feishu is unavailable",
                status_code=503,
            ) from exc

        if response.status_code == 401:
            raise DomainError("FEISHU_AUTH_FAILED", "Feishu authentication failed", status_code=401)
        if response.status_code == 403:
            raise DomainError(
                "FEISHU_PERMISSION_DENIED",
                "Feishu permission denied",
                status_code=403,
            )
        if response.status_code == 429:
            raise DomainError("FEISHU_RATE_LIMITED", "Feishu rate limited", status_code=429)
        try:
            data = response.json()
        except ValueError as exc:
            raise DomainError(
                operation_code,
                "Feishu returned invalid data",
                status_code=502,
            ) from exc
        if not isinstance(data, dict):
            raise DomainError(operation_code, "Feishu request failed", status_code=502)
        api_code = data.get("code", 0)
        if api_code in _AUTH_CODES:
            raise DomainError("FEISHU_AUTH_FAILED", "Feishu authentication failed", status_code=401)
        if api_code in _PERMISSION_CODES:
            raise DomainError(
                "FEISHU_PERMISSION_DENIED", "Feishu permission denied", status_code=403
            )
        if api_code in _RATE_LIMIT_CODES:
            raise DomainError("FEISHU_RATE_LIMITED", "Feishu rate limited", status_code=429)
        if response.is_error or api_code != 0:
            raise DomainError(operation_code, "Feishu request failed", status_code=502)
        return data
