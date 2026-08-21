from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from backend.app.domain.errors import DomainError
from backend.app.export.fake import FakeExportRecorder, FakeFeishuExporter
from backend.app.export.feishu import FeishuApiExporter
from backend.app.export.protocol import EXPORT_HEADERS, CreateRunSheet, ExportRow, SheetRef
from backend.app.export.service import ExportService


def make_rows() -> list[ExportRow]:
    return [
        ExportRow(
            ordinal=1,
            item_id="ITEM-1",
            copy_type="通勤场景",
            title="标题",
            body="正文",
            tags=["气泡水", "#通勤"],
            completion_reason="ai_pass",
            legacy_issues=[],
            change_note="",
        )
    ]


@pytest.mark.asyncio
async def test_fake_exporter_is_stable_and_records_fixed_rows() -> None:
    recorder = FakeExportRecorder()
    exporter = FakeFeishuExporter(recorder)
    request = CreateRunSheet(export_run_id="run-1", sheet_title="输出-1")

    first = await exporter.create_run_sheet(request)
    second = await exporter.create_run_sheet(request)
    await exporter.write_rows(first, make_rows())

    assert first.sheet_id == second.sheet_id == "fake-run-1"
    assert recorder.writes[first.sheet_id][0].to_values() == [
        1,
        "ITEM-1",
        "通勤场景",
        "标题",
        "正文",
        "#气泡水 #通勤",
        "AI 自动通过",
        "",
        "",
    ]


def test_forced_pass_row_requires_and_outputs_legacy_issue() -> None:
    with pytest.raises(ValidationError):
        ExportRow(
            ordinal=1,
            item_id="ITEM-1",
            copy_type="通勤",
            title="标题",
            body="正文",
            completion_reason="forced_pass",
        )

    row = ExportRow(
        ordinal=1,
        item_id="ITEM-1",
        copy_type="通勤",
        title="标题",
        body="正文",
        completion_reason="forced_pass",
        legacy_issues=["仍需法务确认"],
    )
    assert row.to_values()[6:8] == ["强制通过", "仍需法务确认"]

    for display_value in ("AI 自动通过", "人工通过", "强制通过", "强制通过 · 有遗留问题"):
        with pytest.raises(ValidationError):
            ExportRow(
                ordinal=1,
                item_id="ITEM-2",
                copy_type="通勤",
                title="标题",
                body="正文",
                completion_reason=display_value,
                legacy_issues=["不能绕过内部枚举"],
            )


@pytest.mark.asyncio
async def test_feishu_resolves_wiki_creates_sheet_and_overwrites_fixed_range() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/tenant_access_token/internal"):
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "tenant-secret"})
        if request.url.path.endswith("/wiki/v2/spaces/get_node"):
            assert request.url.params["token"] == "wiki-node"
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"node": {"obj_type": "sheet", "obj_token": "spreadsheet"}},
                },
            )
        if request.url.path.endswith("/sheets_batch_update"):
            assert request.url.path == (
                "/open-apis/sheets/v2/spreadsheets/spreadsheet/sheets_batch_update"
            )
            assert request.headers["authorization"] == "Bearer tenant-secret"
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"replies": [{"addSheet": {"properties": {"sheetId": "sheet-a"}}}]},
                },
            )
        if request.url.path.endswith("/values"):
            body = json.loads(request.content)
            assert body["valueRange"]["range"] == "sheet-a!A1:I2"
            assert body["valueRange"]["values"] == [
                list(EXPORT_HEADERS),
                make_rows()[0].to_values(),
            ]
            return httpx.Response(200, json={"code": 0, "data": {"updatedRows": 2}})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        exporter = FeishuApiExporter(
            app_id="app-id",
            app_secret="app-secret",
            wiki_node_token="wiki-node",
            client=client,
            base_url="https://open.feishu.test",
        )
        sheet = await exporter.create_run_sheet(
            CreateRunSheet(export_run_id="run-1", sheet_title="输出-1")
        )
        await exporter.write_rows(sheet, make_rows())

    assert sheet == SheetRef(export_run_id="run-1", sheet_id="sheet-a", title="输出-1")
    assert sum(request.url.path.endswith("/wiki/v2/spaces/get_node") for request in requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (401, {"code": 999}, "FEISHU_AUTH_FAILED"),
        (403, {"code": 999}, "FEISHU_PERMISSION_DENIED"),
        (429, {"code": 999}, "FEISHU_RATE_LIMITED"),
        (500, {"code": 999}, "FEISHU_SHEET_CREATE_FAILED"),
    ],
)
async def test_feishu_maps_errors_without_raw_response(
    status: int, payload: dict[str, int], expected: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/tenant_access_token/internal"):
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "tenant-secret"})
        return httpx.Response(status, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        exporter = FeishuApiExporter(
            app_id="app-id",
            app_secret="do-not-leak",
            spreadsheet_token="spreadsheet",
            client=client,
            base_url="https://open.feishu.test",
        )
        with pytest.raises(DomainError) as error:
            await exporter.create_run_sheet(
                CreateRunSheet(export_run_id="run-1", sheet_title="输出-1")
            )

    assert error.value.code == expected
    assert "do-not-leak" not in str(error.value)
    assert str(payload) not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("api_code", "expected"),
    [
        (99991664, "FEISHU_AUTH_FAILED"),
        (99991672, "FEISHU_PERMISSION_DENIED"),
        (99991400, "FEISHU_RATE_LIMITED"),
    ],
)
async def test_feishu_maps_business_codes(api_code: int, expected: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "tenant-secret", "expire": 7200},
            )
        return httpx.Response(200, json={"code": api_code, "msg": "private vendor detail"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        exporter = FeishuApiExporter(
            app_id="app-id",
            app_secret="do-not-leak",
            spreadsheet_token="spreadsheet",
            client=client,
            base_url="https://open.feishu.test",
        )
        with pytest.raises(DomainError) as error:
            await exporter.create_run_sheet(
                CreateRunSheet(export_run_id="run-1", sheet_title="输出-1")
            )

    assert error.value.code == expected
    assert "private vendor detail" not in str(error.value)


@pytest.mark.asyncio
async def test_feishu_refreshes_expired_token_once_after_401() -> None:
    token_calls = 0
    create_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls, create_calls
        if request.url.path.endswith("/tenant_access_token/internal"):
            token_calls += 1
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": f"tenant-{token_calls}", "expire": 7200},
            )
        create_calls += 1
        if request.headers["authorization"] == "Bearer tenant-1":
            return httpx.Response(401, json={"code": 99991664})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"replies": [{"addSheet": {"properties": {"sheetId": "sheet-a"}}}]},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        exporter = FeishuApiExporter(
            app_id="app-id",
            app_secret="app-secret",
            spreadsheet_token="spreadsheet",
            client=client,
            base_url="https://open.feishu.test",
        )
        result = await exporter.create_run_sheet(
            CreateRunSheet(export_run_id="run-1", sheet_title="输出-1")
        )

    assert result.sheet_id == "sheet-a"
    assert token_calls == 2
    assert create_calls == 2


@pytest.mark.asyncio
async def test_short_lived_tenant_token_is_not_cached_past_its_ttl() -> None:
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.url.path.endswith("/tenant_access_token/internal"):
            token_calls += 1
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": f"tenant-{token_calls}", "expire": 30},
            )
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"replies": [{"addSheet": {"properties": {"sheetId": "sheet-a"}}}]},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        exporter = FeishuApiExporter(
            app_id="app-id",
            app_secret="app-secret",
            spreadsheet_token="spreadsheet",
            client=client,
            base_url="https://open.feishu.test",
        )
        await exporter.create_run_sheet(CreateRunSheet(export_run_id="run-1", sheet_title="输出-1"))
        await exporter.create_run_sheet(CreateRunSheet(export_run_id="run-2", sheet_title="输出-2"))

    assert token_calls == 2


@pytest.mark.asyncio
async def test_feishu_clears_old_tail_rows_when_new_payload_is_shorter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/tenant_access_token/internal"):
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "tenant"})
        body = json.loads(request.content)
        assert body["valueRange"]["range"] == "sheet-a!A1:I4"
        assert body["valueRange"]["values"][2:] == [[""] * 9, [""] * 9]
        return httpx.Response(200, json={"code": 0, "data": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        exporter = FeishuApiExporter(
            app_id="app-id",
            app_secret="app-secret",
            spreadsheet_token="spreadsheet",
            client=client,
            base_url="https://open.feishu.test",
        )
        await exporter.write_rows(
            SheetRef(export_run_id="run-1", sheet_id="sheet-a", title="输出-1"),
            make_rows(),
            clear_through_row=4,
        )


class MemoryExportRepository:
    def __init__(self) -> None:
        self.run: dict[str, object] | None = None

    def create_export_run(
        self,
        export_id: str,
        project_id: str,
        sheet_title: str,
        generation_run_id: str | None = None,
    ) -> dict[str, object]:
        if self.run is None:
            self.run = {
                "id": export_id,
                "project_id": project_id,
                "generation_run_id": generation_run_id,
                "sheet_title": sheet_title,
                "sheet_id": None,
                "status": "pending",
                "row_count": 0,
                "max_written_row": 0,
                "payload_hash": None,
                "row_snapshot_json": None,
                "error_code": None,
            }
        return dict(self.run)

    def update_export_run(self, export_id: str, **values: object) -> dict[str, object]:
        assert self.run is not None and self.run["id"] == export_id
        self.run.update(values)
        return dict(self.run)


class FailFirstWriteExporter(FakeFeishuExporter):
    def __init__(self, recorder: FakeExportRecorder) -> None:
        super().__init__(recorder)
        self.fail = True

    async def write_rows(
        self,
        sheet: SheetRef,
        rows: list[ExportRow],
        *,
        clear_through_row: int = 0,
    ) -> None:
        if self.fail:
            self.fail = False
            raise DomainError("FEISHU_ROWS_WRITE_FAILED", "write failed", status_code=502)
        await super().write_rows(sheet, rows, clear_through_row=clear_through_row)


@pytest.mark.asyncio
async def test_export_service_reuses_existing_sheet_after_failed_write() -> None:
    recorder = FakeExportRecorder()
    repository = MemoryExportRepository()
    service = ExportService(repository, FailFirstWriteExporter(recorder))

    with pytest.raises(DomainError, match="write failed"):
        await service.export_completed(
            export_run_id="run-1",
            project_id="project-1",
            sheet_title="输出-1",
            rows=make_rows(),
        )

    completed = await service.export_completed(
        export_run_id="run-1",
        project_id="project-1",
        sheet_title="输出-1",
        rows=make_rows(),
    )

    assert len(recorder.created) == 1
    assert completed["status"] == "succeeded"
    assert completed["row_count"] == 1


@pytest.mark.asyncio
async def test_successful_export_is_idempotent() -> None:
    recorder = FakeExportRecorder()
    repository = MemoryExportRepository()
    service = ExportService(repository, FakeFeishuExporter(recorder))
    arguments = {
        "export_run_id": "run-1",
        "project_id": "project-1",
        "sheet_title": "输出-1",
        "rows": make_rows(),
    }

    first = await service.export_completed(**arguments)
    second = await service.export_completed(**arguments)

    assert first == second
    assert len(recorder.created) == 1


@pytest.mark.asyncio
async def test_same_export_id_rejects_a_different_row_snapshot() -> None:
    repository = MemoryExportRepository()
    service = ExportService(repository, FakeFeishuExporter())
    await service.export_completed(
        export_run_id="run-1",
        project_id="project-1",
        sheet_title="输出-1",
        rows=make_rows(),
    )
    changed = make_rows()
    changed[0] = changed[0].model_copy(update={"body": "不同正文"})

    with pytest.raises(DomainError) as error:
        await service.export_completed(
            export_run_id="run-1",
            project_id="project-1",
            sheet_title="输出-1",
            rows=changed,
        )

    assert error.value.code == "EXPORT_IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_concurrent_calls_create_only_one_sheet() -> None:
    recorder = FakeExportRecorder()
    repository = MemoryExportRepository()
    first_service = ExportService(repository, FakeFeishuExporter(recorder))
    second_service = ExportService(repository, FakeFeishuExporter(recorder))
    arguments = {
        "export_run_id": "run-concurrent",
        "project_id": "project-1",
        "sheet_title": "输出-1",
        "rows": make_rows(),
    }

    first, second = await asyncio.gather(
        first_service.export_completed(**arguments),
        second_service.export_completed(**arguments),
    )

    assert first["status"] == second["status"] == "succeeded"
    assert len(recorder.created) == 1


class AmbiguousCreateExporter(FakeFeishuExporter):
    async def create_run_sheet(self, request: CreateRunSheet) -> SheetRef:
        await super().create_run_sheet(request)
        raise DomainError(
            "FEISHU_SHEET_CREATE_FAILED",
            "response was lost after remote creation",
            status_code=502,
        )


@pytest.mark.asyncio
async def test_ambiguous_create_reconciles_by_deterministic_sheet_title() -> None:
    recorder = FakeExportRecorder()
    repository = MemoryExportRepository()
    service = ExportService(repository, AmbiguousCreateExporter(recorder))

    result = await service.export_completed(
        export_run_id="run-ambiguous",
        project_id="project-1",
        sheet_title="输出-1",
        rows=make_rows(),
    )

    assert result["status"] == "succeeded"
    assert len(recorder.created) == 1
    assert "run-ambiguous" in recorder.created[0].sheet_title
    assert not any(char in recorder.created[0].sheet_title for char in "/\\?*[]:")


@pytest.mark.asyncio
async def test_export_service_sanitizes_user_sheet_title() -> None:
    recorder = FakeExportRecorder()
    service = ExportService(MemoryExportRepository(), FakeFeishuExporter(recorder))

    await service.export_completed(
        export_run_id="run:special[1]",
        project_id="project-1",
        sheet_title="输出/[特殊]:标题?*",
        rows=make_rows(),
    )

    assert len(recorder.created) == 1
    title = recorder.created[0].sheet_title
    assert not any(char in title for char in "/\\?*[]:")
    assert "run-special-1-" in title
