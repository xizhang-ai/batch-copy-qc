from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from ..db.repositories import Repository
from ..domain.errors import DomainError
from ..qc.merge_rules import merge_rules


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    copy_type_id: str | None = None


def normalize_project_facts(raw: Any) -> dict[str, Any]:
    """Remove UI finding metadata while preserving confirmed fact values."""
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Any] = {}

    def add_fact(key: str, value: Any) -> None:
        clean_key = key.strip()
        if not clean_key:
            return
        if isinstance(value, str):
            clean_value: Any = value.strip()
        elif isinstance(value, (int, float, bool)):
            clean_value = value
        elif isinstance(value, list):
            clean_value = [
                item.strip() if isinstance(item, str) else item
                for item in value
                if not isinstance(item, str) or item.strip()
            ]
        elif isinstance(value, dict) and isinstance(value.get("value"), str):
            clean_value = value["value"].strip()
        else:
            return
        if clean_value in ("", []):
            return
        if clean_key not in normalized:
            normalized[clean_key] = clean_value
        elif not isinstance(normalized[clean_key], list):
            normalized[clean_key] = [normalized[clean_key], clean_value]
        else:
            normalized[clean_key].append(clean_value)

    findings = raw.get("findings")
    if isinstance(findings, list):
        for ordinal, finding in enumerate(findings, start=1):
            if not isinstance(finding, dict):
                continue
            key = str(finding.get("label") or f"fact_{ordinal}")
            add_fact(key, finding.get("value"))
    for key, value in raw.items():
        if key != "findings":
            add_fact(str(key), value)
    return normalized


class GenerationService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def validate(self, project_id: str) -> list[ValidationIssue]:
        project = self.repository.get_project(project_id)
        types = self.repository.list_copy_types(project_id)
        issues: list[ValidationIssue] = []
        if not project["confirmed"]:
            issues.append(
                ValidationIssue("PROJECT_NOT_CONFIRMED", "Save and confirm project content first")
            )
        if not types:
            issues.append(ValidationIssue("COPY_TYPE_REQUIRED", "Add at least one copy type"))
        if sum(row["quantity"] for row in types) > 100:
            issues.append(
                ValidationIssue("COPY_TYPE_TOTAL_EXCEEDED", "Total quantity cannot exceed 100")
            )
        facts = normalize_project_facts(json.loads(project["project_content_json"]))
        if not facts:
            issues.append(ValidationIssue("PROJECT_FACTS_REQUIRED", "Product facts are required"))
        project_rules = [
            rule
            for rule in self.repository.list_rules(project_id)
            if rule["scope"] == "project" and rule["enabled"]
        ]
        for copy_type in types:
            type_rules = [
                rule
                for rule in self.repository.list_rules(project_id)
                if rule["copy_type_id"] == copy_type["id"] and rule["enabled"]
            ]
            for conflict in merge_rules(project_rules, type_rules).conflicts:
                issues.append(
                    ValidationIssue(
                        "HARD_RULE_CONFLICT",
                        f"Hard rule conflict in {conflict.category}",
                        copy_type["id"],
                    )
                )
            if copy_type["use_reference_examples"] and not copy_type["style_profile_confirmed"]:
                issues.append(
                    ValidationIssue(
                        "STYLE_PROFILE_NOT_CONFIRMED",
                        "Confirm the analyzed reference style profile",
                        copy_type["id"],
                    )
                )
            if (
                not copy_type["use_reference_examples"]
                and not copy_type["use_description_requirements"]
                and not copy_type["brief_text"].strip()
            ):
                issues.append(
                    ValidationIssue(
                        "COPY_TYPE_INPUT_REQUIRED",
                        "Copy type needs a brief, references, or description requirements",
                        copy_type["id"],
                    )
                )
        return issues

    def create_run(
        self, project_id: str, *, run_id: str | None = None
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        issues = self.validate(project_id)
        if issues:
            raise DomainError(
                "GENERATION_VALIDATION_FAILED",
                "Generation prerequisites are not met",
                details=[asdict(issue) for issue in issues],
            )
        project = self.repository.get_project(project_id)
        types = self.repository.list_copy_types(project_id)
        rules = self.repository.list_rules(project_id)
        project_rules = [rule for rule in rules if rule["scope"] == "project" and rule["enabled"]]
        snapshot_types: list[dict[str, Any]] = []
        for copy_type in types:
            type_rules = [
                rule
                for rule in rules
                if rule["copy_type_id"] == copy_type["id"] and rule["enabled"]
            ]
            merged = merge_rules(project_rules, type_rules)
            snapshot_types.append(
                {
                    **copy_type,
                    "reference_examples": self.repository.list_references(copy_type["id"]),
                    "effective_rules": merged.effective,
                    "rule_conflicts": [asdict(conflict) for conflict in merged.conflicts],
                }
            )
        snapshot = {"project": project, "copy_types": snapshot_types, "rules": rules}
        requested = sum(copy_type["quantity"] for copy_type in types)
        run = self.repository.create_generation_run(
            project_id, requested, snapshot, run_id=run_id or str(uuid4())
        )
        items = [
            self.repository.create_item_slot(run["id"], copy_type["id"], ordinal)
            for copy_type in types
            for ordinal in range(1, copy_type["quantity"] + 1)
        ]
        return run, items

    def summary(self, run_id: str) -> dict[str, Any]:
        run = self.repository.get_run(run_id)
        items = self.repository.list_items(run_id=run_id)
        counts = {
            status: sum(item["generation_status"] == status for item in items)
            for status in ("queued", "running", "generated", "failed")
        }
        pending = counts["queued"] + counts["running"]
        if pending:
            status = "running" if counts["running"] or counts["generated"] else "queued"
        elif counts["failed"] and counts["generated"]:
            status = "partial_failed"
        elif counts["failed"]:
            status = "failed"
        else:
            status = "completed"
        if run["status"] != status:
            self.repository.connection.execute(
                "UPDATE generation_runs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, run_id),
            )
            self.repository.connection.commit()
            run["status"] = status
        return {
            **run,
            "requested": run["requested_count"],
            "total_requested": run["requested_count"],
            "generated": counts["generated"],
            "failed": counts["failed"],
            "pending": pending,
            "errors": sorted({item["error_code"] for item in items if item["error_code"]}),
            "item_ids": [item["id"] for item in items],
        }
