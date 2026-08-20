from __future__ import annotations

from dataclasses import dataclass, field

from .protocol import CreateRunSheet, ExportRow, SheetRef


@dataclass
class FakeExportRecorder:
    created: list[CreateRunSheet] = field(default_factory=list)
    writes: dict[str, list[ExportRow]] = field(default_factory=dict)


class FakeFeishuExporter:
    adapter_name = "fake"

    def __init__(self, recorder: FakeExportRecorder | None = None) -> None:
        self.recorder = recorder or FakeExportRecorder()

    async def find_run_sheet(self, request: CreateRunSheet) -> SheetRef | None:
        for existing in self.recorder.created:
            if existing.sheet_title == request.sheet_title:
                return SheetRef(
                    export_run_id=request.export_run_id,
                    sheet_id=f"fake-{existing.export_run_id}",
                    title=existing.sheet_title,
                )
        return None

    async def create_run_sheet(self, request: CreateRunSheet) -> SheetRef:
        self.recorder.created.append(request.model_copy(deep=True))
        return SheetRef(
            export_run_id=request.export_run_id,
            sheet_id=f"fake-{request.export_run_id}",
            title=request.sheet_title,
        )

    async def write_rows(
        self,
        sheet: SheetRef,
        rows: list[ExportRow],
        *,
        clear_through_row: int = 0,
    ) -> None:
        self.recorder.writes[sheet.sheet_id] = [row.model_copy(deep=True) for row in rows]
