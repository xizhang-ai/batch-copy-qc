from __future__ import annotations

import json
from typing import Any

from ..db.repositories import Repository
from ..domain.errors import DomainError
from ..domain.schemas import SelectionRewriteContext
from ..qc.deterministic import run_deterministic_qc


class ReviewService:
    def __init__(self, repository: Repository, model_adapter: Any, qc_service: Any = None) -> None:
        self.repository = repository
        self.model_adapter = model_adapter
        self.qc_service = qc_service

    def _require_human_review(self, item_id: str) -> dict[str, Any]:
        item = self.repository.get_item(item_id)
        if item["workflow_status"] != "human_review":
            raise DomainError(
                "ITEM_NOT_IN_HUMAN_REVIEW", "Item is not in human review", status_code=409
            )
        return item

    async def _recheck(self, item_id: str) -> dict[str, Any]:
        if self.qc_service is None:
            raise DomainError(
                "QC_SERVICE_UNAVAILABLE", "QC service is unavailable", status_code=503
            )
        return await self.qc_service.recheck_human_review(item_id)

    async def edit(
        self,
        item_id: str,
        *,
        expected_version: int,
        title: str,
        body: str,
        tags: list[str],
        change_note: str = "",
    ) -> dict[str, Any]:
        self._require_human_review(item_id)
        updated = self.repository.append_version(
            item_id,
            title,
            body,
            tags,
            "human_edit",
            expected_version=expected_version,
            change_note=change_note,
        )
        self.repository.add_review_event(item_id, "edit", change_note)
        return await self._recheck(updated["id"])

    async def rewrite_selection(
        self,
        item_id: str,
        *,
        expected_version: int,
        field: str,
        selection_start: int,
        selection_end: int,
        selected_text: str,
        instruction: str,
    ) -> dict[str, Any]:
        item = self._require_human_review(item_id)
        if item["current_version"] != expected_version:
            raise DomainError(
                "ITEM_VERSION_CONFLICT",
                "Item version changed",
                details={"current_version": item["current_version"]},
                status_code=409,
            )
        if field not in {"title", "body"}:
            raise DomainError("SELECTION_FIELD_INVALID", "Only title and body can be rewritten")
        content = item["content"]
        current = content[field]
        if (
            selection_start < 0
            or selection_end <= selection_start
            or selection_end > len(current)
            or current[selection_start:selection_end] != selected_text
        ):
            raise DomainError(
                "SELECTION_STALE",
                "Selected text no longer matches the current version",
                status_code=409,
            )
        replacement = await self.model_adapter.rewrite_selection(
            SelectionRewriteContext(
                field=field, selected_text=selected_text, context=current, direction=instruction
            )
        )
        new_text = current[:selection_start] + replacement + current[selection_end:]
        title = new_text if field == "title" else content["title"]
        body = new_text if field == "body" else content["body"]
        updated = self.repository.append_version(
            item_id,
            title,
            body,
            json.loads(content["tags_json"]),
            "human_selection",
            expected_version=expected_version,
            change_note=instruction,
        )
        self.repository.add_review_event(item_id, "rewrite_selection", instruction)
        return await self._recheck(updated["id"])

    def decide(
        self, item_id: str, action: str, reason: str = "", legacy_issues: list[str] | None = None
    ) -> dict[str, Any]:
        item = self.repository.get_item(item_id)
        if action == "recall":
            if item["workflow_status"] != "completed":
                raise DomainError(
                    "ITEM_RECALL_INVALID", "Only completed items can be recalled", status_code=409
                )
            recalled = self.repository.cas_item_state(item_id, "completed", "human_review")
            self.repository.add_review_event(item_id, "recall", reason)
            return recalled
        item = self._require_human_review(item_id)
        if action == "reject":
            self.repository.connection.execute(
                "UPDATE copy_items SET review_disposition='rejected',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (item_id,),
            )
            self.repository.connection.commit()
            self.repository.add_review_event(item_id, "reject", reason)
            return self.repository.get_item(item_id)
        unresolved = self.repository.unresolved_findings(item_id)
        hard = [finding for finding in unresolved if finding["level"] == "hard"]
        if action == "pass":
            content = item["content"]
            fresh_hard = [
                finding
                for finding in run_deterministic_qc(
                    {
                        "title": content["title"],
                        "body": content["body"],
                        "tags": json.loads(content["tags_json"]),
                    }
                )
                if finding.level == "hard"
            ]
            system_failures = [finding for finding in unresolved if finding["source"] == "system"]
            if system_failures or item["error_code"]:
                raise DomainError(
                    "QC_RECHECK_INCOMPLETE",
                    "A successful QC recheck is required before passing",
                    status_code=409,
                )
            if hard or fresh_hard:
                raise DomainError(
                    "HARD_FINDINGS_UNRESOLVED",
                    "Resolve hard findings before passing",
                    status_code=409,
                )
            completed = self.repository.cas_item_state(
                item_id, "human_review", "completed", "human_pass"
            )
            self.repository.add_review_event(item_id, "pass", reason)
            return completed
        if action == "force_pass":
            clean_reason = reason.strip()
            inherited = [finding["message"].strip() for finding in unresolved]
            supplied = [str(issue).strip() for issue in (legacy_issues or [])]
            issues = list(dict.fromkeys(issue for issue in [*inherited, *supplied] if issue))
            if not issues:
                raise DomainError(
                    "FORCE_PASS_ISSUES_REQUIRED", "Forced pass requires legacy issues"
                )
            if not clean_reason:
                raise DomainError(
                    "FORCE_PASS_REASON_REQUIRED", "Forced pass requires a non-empty reason"
                )
            completed = self.repository.cas_item_state(
                item_id, "human_review", "completed", "forced_pass"
            )
            self.repository.add_review_event(item_id, "force_pass", clean_reason, issues)
            return completed
        raise DomainError("REVIEW_ACTION_INVALID", "Unknown review action")
