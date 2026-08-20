from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..domain.enums import CompletionReason

EXPORT_HEADERS: tuple[str, ...] = (
    "序号",
    "item_id",
    "文案类型",
    "标题",
    "正文",
    "话题标签",
    "完成方式",
    "遗留问题",
    "修改说明",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRunSheet(_StrictModel):
    export_run_id: str = Field(min_length=1)
    sheet_title: str = Field(min_length=1, max_length=100)


class SheetRef(_StrictModel):
    export_run_id: str = Field(min_length=1)
    sheet_id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class ExportRow(_StrictModel):
    ordinal: int = Field(ge=1)
    item_id: str = Field(min_length=1)
    copy_type: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    completion_reason: CompletionReason
    legacy_issues: list[str] = Field(default_factory=list)
    change_note: str = ""

    @model_validator(mode="after")
    def forced_pass_requires_legacy_issues(self) -> ExportRow:
        if self.completion_reason == CompletionReason.FORCED_PASS and not any(
            issue.strip() for issue in self.legacy_issues
        ):
            raise ValueError("Forced pass requires at least one legacy issue")
        return self

    def to_values(self) -> list[str | int]:
        completion_labels = {
            CompletionReason.AI_PASS: "AI 自动通过",
            CompletionReason.HUMAN_PASS: "人工通过",
            CompletionReason.FORCED_PASS: "强制通过",
        }
        return [
            self.ordinal,
            self.item_id,
            self.copy_type,
            self.title,
            self.body,
            " ".join(self.tags),
            completion_labels[self.completion_reason],
            "；".join(self.legacy_issues),
            self.change_note,
        ]


@runtime_checkable
class FeishuExporter(Protocol):
    async def find_run_sheet(self, request: CreateRunSheet) -> SheetRef | None: ...

    async def create_run_sheet(self, request: CreateRunSheet) -> SheetRef: ...

    async def write_rows(
        self,
        sheet: SheetRef,
        rows: list[ExportRow],
        *,
        clear_through_row: int = 0,
    ) -> None: ...
