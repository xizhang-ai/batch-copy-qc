from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..db.repositories import Repository
from ..domain.enums import BriefScope
from ..domain.errors import DomainError
from .extraction import extract_text, normalize_text


class BriefService:
    def __init__(self, repository: Repository, model_adapter: Any) -> None:
        self.repository = repository
        self.model_adapter = model_adapter

    async def parse_text(
        self,
        project_id: str,
        text: str,
        *,
        scope: BriefScope = BriefScope.PROJECT,
        copy_type_id: str | None = None,
        display_name: str = "pasted-text",
        stored_name: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_text(text)
        if not normalized:
            raise DomainError("BRIEF_TEXT_EMPTY", "Brief contains no readable text")
        source = self.repository.create_brief_source(
            project_id=project_id,
            copy_type_id=copy_type_id,
            source_kind="file" if stored_name else "text",
            display_name=display_name,
            stored_name=stored_name,
            raw_text=normalized,
        )
        return await self._parse_source(project_id, source["id"], normalized, scope)

    async def _parse_source(
        self,
        project_id: str,
        source_id: str,
        text: str,
        scope: BriefScope,
    ) -> dict[str, Any]:
        try:
            parsed = await self.model_adapter.parse_brief(text, scope=scope)
        except DomainError as exc:
            self.repository.finish_brief_source(source_id, error_code=exc.code)
            raise
        except Exception as exc:
            self.repository.finish_brief_source(source_id, error_code="BRIEF_PARSE_FAILED")
            raise DomainError(
                "BRIEF_PARSE_FAILED", "Brief could not be parsed", status_code=503
            ) from exc
        payload = parsed.model_dump(mode="json")
        self.repository.finish_brief_source(source_id, parsed=payload)
        project = self.repository.get_project(project_id)
        has_confirmed_content = bool(project["confirmed"])
        section_names = {
            "project_content": "project_content",
            "copy_requirements": "copy_requirements",
            "project_qc": "qc_requirements",
            "conflicts": "needs_confirmation",
        }
        findings = []
        for source_section, target_section in section_names.items():
            for finding in payload["sections"].get(source_section, []):
                findings.append(
                    {
                        "id": str(uuid4()),
                        "section": target_section,
                        "label": finding["section"],
                        "value": finding["value"],
                        "evidence": finding["source_quote"],
                        "confidence": (
                            "high"
                            if finding["confidence"] >= 0.8
                            else "medium"
                            if finding["confidence"] >= 0.5
                            else "low"
                        ),
                    }
                )
        return {
            "source_id": source_id,
            "source_name": payload.get("source_name") or "粘贴文本",
            "findings": findings,
            "sections": payload["sections"],
            "copy_type_fields": payload.get("copy_type_fields"),
            "project_change_suggestions": payload.get("project_change_suggestions", []),
            "suggested_changes": payload["sections"] if has_confirmed_content else {},
            "conflicts": payload["sections"].get("conflicts", []),
        }

    async def parse_file(self, project_id: str, path: str, **kwargs: Any) -> dict[str, Any]:
        scope = kwargs.get("scope", BriefScope.PROJECT)
        source = self.repository.create_brief_source(
            project_id=project_id,
            copy_type_id=kwargs.get("copy_type_id"),
            source_kind="file",
            display_name=kwargs.get("display_name", "uploaded-file"),
            stored_name=kwargs.get("stored_name"),
            raw_text="",
        )
        try:
            text = extract_text(path)
        except DomainError as exc:
            self.repository.finish_brief_source(source["id"], error_code=exc.code)
            raise
        self.repository.set_brief_source_text(source["id"], text)
        return await self._parse_source(project_id, source["id"], text, scope)
