from __future__ import annotations

from typing import Any

from ..db.repositories import Repository


def _rule_level(value: dict[str, Any], statement: str) -> str:
    explicit = str(value.get("level", "")).lower()
    if explicit in {"hard", "soft"}:
        return explicit
    hard_markers = ("禁止", "不得", "严禁", "不能", "must_avoid", "禁用")
    return "hard" if any(marker in statement for marker in hard_markers) else "soft"


def materialize_brief_qc_rules(
    repository: Repository,
    project_id: str,
    findings: list[dict[str, Any]],
    *,
    scope: str = "project",
    copy_type_id: str | None = None,
    source_kind: str = "derived_project_brief",
) -> None:
    """Create editable QC rules once for confirmed Brief findings."""
    existing = repository.list_rules(project_id)
    existing_keys = {
        (rule["copy_type_id"], rule["category"], rule["statement"].strip()) for rule in existing
    }
    existing_evidence = {
        (rule["copy_type_id"], rule["source_kind"], rule["source_evidence"].strip())
        for rule in existing
        if rule["source_evidence"].strip()
    }
    for finding in findings:
        statement = str(finding.get("value") or "").strip()
        if not statement:
            continue
        category = str(finding.get("label") or finding.get("section") or "brief_qc").strip()
        key = (copy_type_id, category, statement)
        evidence = str(finding.get("evidence") or finding.get("source_quote") or "").strip()
        evidence_key = (copy_type_id, source_kind, evidence)
        if key in existing_keys or (evidence and evidence_key in existing_evidence):
            continue
        repository.create_rule(
            project_id,
            copy_type_id=copy_type_id,
            scope=scope,
            level=_rule_level(finding, statement),
            category=category,
            statement=statement,
            source_evidence=evidence,
            source_kind=source_kind,
        )
        existing_keys.add(key)
        if evidence:
            existing_evidence.add(evidence_key)
