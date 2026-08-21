from __future__ import annotations

import asyncio
import json
from typing import Any

from ..db.repositories import Repository
from ..domain.errors import DomainError
from ..domain.schemas import (
    CopyDraft,
    ModelQcFinding,
    RewriteContext,
    SemanticQcContext,
    SemanticQcRule,
)
from ..generation.service import normalize_project_facts
from .deterministic import QcFinding, run_deterministic_qc
from .similarity import compare_items, compare_with_references


class QcService:
    def __init__(
        self,
        repository: Repository,
        model_adapter: Any,
        *,
        auto_rewrite_limit: int = 4,
        retry_limit: int = 2,
        confidence_threshold: float = 0.7,
        similarity_threshold: int = 85,
    ) -> None:
        self.repository = repository
        self.model_adapter = model_adapter
        self.auto_rewrite_limit = auto_rewrite_limit
        self.retry_limit = retry_limit
        self.confidence_threshold = confidence_threshold
        self.similarity_threshold = similarity_threshold

    async def _semantic(self, context: SemanticQcContext):
        last_error: Exception | None = None
        for attempt in range(self.retry_limit + 1):
            try:
                return await self.model_adapter.run_semantic_qc(context)
            except DomainError as exc:
                last_error = exc
                if (
                    exc.code
                    not in {
                        "MODEL_RATE_LIMITED",
                        "MODEL_TIMEOUT",
                        "MODEL_UNAVAILABLE",
                        "MODEL_RESPONSE_INVALID",
                    }
                    or attempt == self.retry_limit
                ):
                    raise
                await asyncio.sleep(min(2**attempt, 10))
        raise last_error or RuntimeError("semantic qc failed")

    def _snapshot_context(
        self, item: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], CopyDraft]:
        run = self.repository.get_run(item["run_id"])
        snapshot = json.loads(run["configuration_snapshot_json"])
        copy_type = next(row for row in snapshot["copy_types"] if row["id"] == item["copy_type_id"])
        content = item["content"]
        draft = CopyDraft(
            title=content["title"],
            body=content["body"],
            tags=json.loads(content["tags_json"]),
        )
        return snapshot, copy_type, draft

    def _similarity_findings(
        self,
        item: dict[str, Any],
        draft: CopyDraft,
        copy_type: dict[str, Any],
        *,
        include_all_items: bool,
    ) -> list[QcFinding]:
        ordered_items = self.repository.list_items(run_id=item["run_id"])
        current_index = next(
            index for index, candidate in enumerate(ordered_items) if candidate["id"] == item["id"]
        )
        candidates = (
            [candidate for candidate in ordered_items if candidate["id"] != item["id"]]
            if include_all_items
            else ordered_items[:current_index]
        )
        comparable = [
            {
                "id": candidate["id"],
                "title": candidate["content"]["title"],
                "body": candidate["content"]["body"],
            }
            for candidate in candidates
            if candidate["content"]
        ]
        matches = compare_items(
            {"id": item["id"], "title": draft.title, "body": draft.body},
            comparable,
            self.similarity_threshold,
        )
        matches.extend(
            compare_with_references(
                {"id": item["id"], "title": draft.title, "body": draft.body},
                copy_type["reference_examples"],
                self.similarity_threshold,
            )
        )
        return [
            QcFinding(
                "similarity",
                (
                    f"与同批文案 {match.matched_id} 相似度过高"
                    if match.source_kind == "batch_item"
                    else f"与参考文案 {match.matched_id} 相似度过高"
                ),
                "hard",
                f"score={match.score}",
                suggestion="重写标题切入、段落结构和表达方式，同时保留已确认的项目事实。",
                auto_fixable=True,
                source="similarity",
                matched_id=match.matched_id,
            )
            for match in matches
        ]

    @staticmethod
    def _semantic_rules(copy_type: dict[str, Any]) -> list[SemanticQcRule]:
        return [
            SemanticQcRule(
                id=rule["id"],
                level=rule["level"],
                category=rule["category"],
                requirement=rule["statement"],
            )
            for rule in copy_type["effective_rules"]
            if rule.get("enabled", True)
        ]

    @staticmethod
    def _matched_rule(
        finding: ModelQcFinding, rules: list[SemanticQcRule]
    ) -> SemanticQcRule | None:
        by_id = {rule.id: rule for rule in rules}
        if finding.rule_id in by_id:
            return by_id[finding.rule_id]
        if finding.rule_index is not None and finding.rule_index < len(rules):
            return rules[finding.rule_index]
        if finding.violated_rule:
            exact = [
                rule for rule in rules if rule.requirement.strip() == finding.violated_rule.strip()
            ]
            if len(exact) == 1:
                return exact[0]
        code = finding.code.strip().lower()
        category_matches = [rule for rule in rules if rule.category.strip().lower() == code]
        return category_matches[0] if len(category_matches) == 1 else None

    async def _evaluate(
        self, item: dict[str, Any], *, include_all_items: bool = False
    ) -> tuple[list[QcFinding], float, dict[str, Any], CopyDraft]:
        snapshot, copy_type, draft = self._snapshot_context(item)
        deterministic = run_deterministic_qc(
            draft,
            rules=copy_type["effective_rules"],
            must_include=json.loads(copy_type["must_include_json"]),
            must_avoid=json.loads(copy_type["must_avoid_json"]),
        )
        deterministic.extend(
            self._similarity_findings(item, draft, copy_type, include_all_items=include_all_items)
        )
        semantic_rules = self._semantic_rules(copy_type)
        semantic = await self._semantic(
            SemanticQcContext(
                draft=draft,
                project_facts=normalize_project_facts(
                    json.loads(snapshot["project"]["project_content_json"])
                ),
                rules=semantic_rules,
                similarity_context=[
                    finding.message for finding in deterministic if finding.category == "similarity"
                ],
            )
        )
        model_findings: list[QcFinding] = []
        has_deterministic_similarity = any(
            finding.category == "similarity" for finding in deterministic
        )
        duplicate_similarity_codes = {
            "similarity",
            "similarity_too_high",
            "similarity_too_close",
        }
        for finding in semantic.findings:
            matched_rule = self._matched_rule(finding, semantic_rules)
            # Similarity is calculated deterministically with RapidFuzz. Drop only the
            # model's exact, unlinked echo; a finding attached to a real rule is an
            # independent policy violation and must never be hidden by deduplication.
            if (
                has_deterministic_similarity
                and matched_rule is None
                and finding.code.strip().lower() in duplicate_similarity_codes
            ):
                continue
            level = (
                matched_rule.level
                if matched_rule
                else "hard"
                if finding.severity == "error"
                else "soft"
            )
            model_findings.append(
                QcFinding(
                    finding.code,
                    finding.message,
                    level,
                    finding.evidence or "",
                    finding.suggestion or "",
                    finding.auto_fixable,
                    matched_rule.id if matched_rule else finding.rule_id,
                    "semantic",
                )
            )
        if semantic.confidence < self.confidence_threshold:
            model_findings.append(
                QcFinding(
                    "low_confidence",
                    "AI QC confidence is below the review threshold",
                    "soft",
                    evidence=f"confidence={semantic.confidence:.2f}",
                    auto_fixable=False,
                    source="semantic",
                )
            )
        return [*deterministic, *model_findings], semantic.confidence, copy_type, draft

    def _store_successful_evaluation(self, item: dict[str, Any], findings: list[QcFinding]) -> None:
        qc_run_id = self.repository.create_qc_run(item["id"], item["current_version"], "completed")
        new_findings = self.repository.reconcile_findings(item["id"], findings)
        self.repository.add_findings(qc_run_id, item["id"], new_findings)

    async def recheck_human_review(self, item_id: str) -> dict[str, Any]:
        item = self.repository.get_item(item_id)
        if item["workflow_status"] != "human_review":
            raise DomainError(
                "ITEM_NOT_IN_HUMAN_REVIEW", "Item is not in human review", status_code=409
            )
        try:
            findings, _confidence, _copy_type, _draft = await self._evaluate(
                item, include_all_items=True
            )
        except DomainError as exc:
            qc_run_id = self.repository.create_qc_run(item_id, item["current_version"], "failed")
            self.repository.add_findings(
                qc_run_id,
                item_id,
                [
                    QcFinding(
                        "system_error",
                        f"QC unavailable: {exc.code}",
                        "soft",
                        auto_fixable=False,
                        source="system",
                    )
                ],
            )
            self.repository.set_item_error(item_id, exc.code)
            return self.repository.get_item(item_id)
        self._store_successful_evaluation(item, findings)
        self.repository.set_item_error(item_id, None)
        return self.repository.get_item(item_id)

    async def run(self, item_id: str) -> dict[str, Any]:
        item = self.repository.get_item(item_id)
        if item["workflow_status"] == "completed":
            return item
        if item["workflow_status"] == "pending_ai_qc":
            item = self.repository.cas_item_state(item_id, "pending_ai_qc", "ai_qc_running")
        elif item["workflow_status"] != "ai_qc_running":
            raise DomainError("ITEM_NOT_QC_READY", "Item is not ready for AI QC", status_code=409)
        if not item["content"]:
            return self.repository.cas_item_state(
                item_id, "ai_qc_running", "human_review", error_code="ITEM_CONTENT_MISSING"
            )
        try:
            findings, confidence, copy_type, draft = await self._evaluate(item)
        except DomainError as exc:
            finding = QcFinding(
                "system_error",
                f"QC unavailable: {exc.code}",
                "soft",
                auto_fixable=False,
                source="system",
            )
            qc_run_id = self.repository.create_qc_run(item_id, item["current_version"], "failed")
            self.repository.add_findings(qc_run_id, item_id, [finding])
            return self.repository.cas_item_state(
                item_id, "ai_qc_running", "human_review", error_code=exc.code
            )
        self._store_successful_evaluation(item, findings)
        if not findings and confidence >= self.confidence_threshold:
            completed = self.repository.cas_item_state(
                item_id, "ai_qc_running", "completed", "ai_pass"
            )
            self.repository.add_review_event(item_id, "ai_pass")
            return completed
        # A hard rule is non-overridable, but text findings can still be sent through
        # up to auto_rewrite_limit constrained repair attempts. Model/system failures
        # return earlier; low-confidence evaluations still require a person immediately.
        # Persistent findings move to human review after auto_rewrite_limit is reached.
        requires_human = confidence < self.confidence_threshold
        if requires_human or item["auto_rewrite_count"] >= self.auto_rewrite_limit:
            return self.repository.cas_item_state(item_id, "ai_qc_running", "human_review")
        rewriting = self.repository.cas_item_state(item_id, "ai_qc_running", "ai_rewrite_running")
        rewritten = await self.model_adapter.rewrite_copy(
            RewriteContext(
                draft=draft,
                findings=[
                    ModelQcFinding(
                        code=finding.category,
                        message=finding.message,
                        severity="error" if finding.level == "hard" else "warning",
                        rule_id=finding.rule_id,
                        evidence=finding.evidence,
                        suggestion=finding.suggestion,
                        auto_fixable=finding.auto_fixable,
                    )
                    for finding in findings
                ],
                hard_rules=[
                    rule["statement"]
                    for rule in copy_type["effective_rules"]
                    if rule["level"] == "hard"
                ],
            )
        )
        return self.repository.append_auto_rewrite(
            item_id,
            rewritten.title,
            rewritten.body,
            rewritten.tags,
            expected_version=item["current_version"],
            expected_rewrite_count=rewriting["auto_rewrite_count"],
            change_note="AI QC auto-fix",
        )
