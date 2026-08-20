from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any, Protocol

from ..domain.errors import DomainError
from .protocol import CreateRunSheet, ExportRow, FeishuExporter, SheetRef


class ExportRepository(Protocol):
    def create_export_run(
        self,
        export_id: str,
        project_id: str,
        sheet_title: str,
        generation_run_id: str | None = None,
    ) -> dict[str, Any]: ...

    def update_export_run(self, export_id: str, **values: Any) -> dict[str, Any]: ...


_EXPORT_LOCKS: dict[str, asyncio.Lock] = {}


def _lock_for(export_run_id: str) -> asyncio.Lock:
    return _EXPORT_LOCKS.setdefault(export_run_id, asyncio.Lock())


def _remote_sheet_title(sheet_title: str, export_run_id: str) -> str:
    safe_title = re.sub(r"[/\\?*\[\]:]", "-", sheet_title).strip() or "文案输出"
    safe_id = re.sub(r"[^0-9A-Za-z_-]", "-", export_run_id)
    suffix = f" - {safe_id}"
    return f"{safe_title[: max(1, 100 - len(suffix))]}{suffix}"


def _payload_snapshot(
    *,
    project_id: str,
    generation_run_id: str | None,
    sheet_title: str,
    rows: list[ExportRow],
) -> tuple[str, str]:
    payload = {
        "project_id": project_id,
        "generation_run_id": generation_run_id,
        "sheet_title": sheet_title,
        "columns_version": 1,
        "rows": [row.model_dump(mode="json") for row in rows],
    }
    snapshot = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return snapshot, hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


class ExportService:
    def __init__(self, repository: ExportRepository, exporter: FeishuExporter) -> None:
        self._repository = repository
        self._exporter = exporter

    async def export_completed(
        self,
        *,
        export_run_id: str,
        project_id: str,
        sheet_title: str,
        rows: list[ExportRow],
        generation_run_id: str | None = None,
    ) -> dict[str, Any]:
        async with _lock_for(export_run_id):
            ordered_rows = sorted(rows, key=lambda row: (row.ordinal, row.item_id))
            snapshot, payload_hash = _payload_snapshot(
                project_id=project_id,
                generation_run_id=generation_run_id,
                sheet_title=sheet_title,
                rows=ordered_rows,
            )
            run = self._repository.create_export_run(
                export_run_id,
                project_id,
                sheet_title,
                generation_run_id,
            )
            if (
                run["project_id"] != project_id
                or run["sheet_title"] != sheet_title
                or run.get("generation_run_id") != generation_run_id
            ):
                raise DomainError(
                    "EXPORT_IDEMPOTENCY_CONFLICT",
                    "Export id is already bound to a different request",
                    status_code=409,
                )
            existing_hash = run.get("payload_hash")
            if existing_hash and existing_hash != payload_hash:
                raise DomainError(
                    "EXPORT_IDEMPOTENCY_CONFLICT",
                    "Export id is already bound to a different row snapshot",
                    status_code=409,
                )
            if not existing_hash:
                run = self._repository.update_export_run(
                    export_run_id,
                    payload_hash=payload_hash,
                    row_snapshot_json=snapshot,
                )
            if run["status"] == "succeeded":
                return run

            remote_title = _remote_sheet_title(sheet_title, export_run_id)
            request = CreateRunSheet(export_run_id=export_run_id, sheet_title=remote_title)
            try:
                sheet_id = run.get("sheet_id")
                if not sheet_id:
                    sheet = await self._exporter.find_run_sheet(request)
                    if sheet is None:
                        try:
                            sheet = await self._exporter.create_run_sheet(request)
                        except DomainError:
                            sheet = await self._exporter.find_run_sheet(request)
                            if sheet is None:
                                raise
                    run = self._repository.update_export_run(
                        export_run_id,
                        sheet_id=sheet.sheet_id,
                        status="running",
                        error_code=None,
                    )
                else:
                    sheet = SheetRef(
                        export_run_id=export_run_id,
                        sheet_id=sheet_id,
                        title=remote_title,
                    )
                previous_max_row = int(run.get("max_written_row") or 0)
                await self._exporter.write_rows(
                    sheet,
                    ordered_rows,
                    clear_through_row=previous_max_row,
                )
                return self._repository.update_export_run(
                    export_run_id,
                    status="succeeded",
                    row_count=len(ordered_rows),
                    max_written_row=len(ordered_rows) + 1,
                    error_code=None,
                )
            except DomainError as exc:
                self._repository.update_export_run(
                    export_run_id,
                    status="failed",
                    error_code=exc.code,
                )
                raise
