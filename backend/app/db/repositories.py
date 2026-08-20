from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from typing import Any
from uuid import uuid4

from ..domain.errors import DomainError


def new_id() -> str:
    return str(uuid4())


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def decode_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_project(self, name: str, *, brand: str = "", category: str = "") -> dict[str, Any]:
        project_id = new_id()
        self.connection.execute(
            "INSERT INTO projects(id,name,brand,category) VALUES (?,?,?,?)",
            (project_id, name, brand, category),
        )
        self.connection.commit()
        return self.get_project(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute("SELECT * FROM projects ORDER BY created_at")
        ]

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise DomainError("PROJECT_NOT_FOUND", "Project not found", status_code=404)
        return dict(row)

    def update_project(self, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "name",
            "category",
            "brand",
            "product_sku",
            "project_content_json",
            "copy_requirements_json",
            "qc_requirements_json",
            "pending_confirmation_json",
            "confirmed",
        }
        data = {key: value for key, value in values.items() if key in allowed}
        for key in tuple(data):
            if key.endswith("_json") and not isinstance(data[key], str):
                data[key] = _json(data[key])
        if data:
            assignment = ",".join(f"{key}=?" for key in data)
            self.connection.execute(
                f"UPDATE projects SET {assignment},updated_at=CURRENT_TIMESTAMP WHERE id=?",  # noqa: S608
                (*data.values(), project_id),
            )
            self.connection.commit()
        return self.get_project(project_id)

    def create_brief_source(self, **values: Any) -> dict[str, Any]:
        source_id = new_id()
        self.connection.execute(
            "INSERT INTO brief_sources(id,project_id,copy_type_id,source_kind,display_name,stored_name,raw_text,parse_status) VALUES (?,?,?,?,?,?,?,?)",
            (
                source_id,
                values["project_id"],
                values.get("copy_type_id"),
                values["source_kind"],
                values.get("display_name", "pasted-text"),
                values.get("stored_name"),
                values.get("raw_text", ""),
                values.get("parse_status", "pending"),
            ),
        )
        self.connection.commit()
        return dict(
            self.connection.execute(
                "SELECT * FROM brief_sources WHERE id=?", (source_id,)
            ).fetchone()
        )

    def finish_brief_source(
        self, source_id: str, *, parsed: Any = None, error_code: str | None = None
    ) -> None:
        status = "failed" if error_code else "parsed"
        self.connection.execute(
            "UPDATE brief_sources SET parsed_json=?,parse_status=?,error_code=? WHERE id=?",
            (_json(parsed) if parsed is not None else None, status, error_code, source_id),
        )
        self.connection.commit()

    def set_brief_source_text(self, source_id: str, raw_text: str) -> None:
        self.connection.execute(
            "UPDATE brief_sources SET raw_text=? WHERE id=?", (raw_text, source_id)
        )
        self.connection.commit()

    def count_brief_sources(self, project_id: str) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM brief_sources WHERE project_id=?", (project_id,)
            ).fetchone()[0]
        )

    def list_classified_brief_sources(self, project_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM brief_sources "
                "WHERE project_id=? AND classification_json IS NOT NULL "
                "ORDER BY created_at,id",
                (project_id,),
            )
        ]

    def get_brief_source(self, source_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM brief_sources WHERE id=?", (source_id,)
        ).fetchone()
        if not row:
            raise DomainError("BRIEF_SOURCE_NOT_FOUND", "Brief source not found", status_code=404)
        return dict(row)

    def classify_brief_source(
        self, source_id: str, copy_type_id: str | None, classification: Any
    ) -> dict[str, Any]:
        source = self.get_brief_source(source_id)
        merged = (
            json.loads(source["classification_json"]) if source.get("classification_json") else {}
        )
        if isinstance(classification, dict):
            merged.update(classification)
        if copy_type_id:
            copy_type = self.get_copy_type(copy_type_id)
            if copy_type["project_id"] != source["project_id"]:
                raise DomainError(
                    "COPY_TYPE_PROJECT_MISMATCH",
                    "Copy type does not belong to the brief project",
                    status_code=409,
                )
            merged["assigned_type_id"] = copy_type_id
        else:
            merged["assigned_type_id"] = None
        self.connection.execute(
            "UPDATE brief_sources SET copy_type_id=?,classification_json=? WHERE id=?",
            (copy_type_id, _json(merged), source_id),
        )
        self.connection.commit()
        return self.get_brief_source(source_id)

    def create_copy_type(self, project_id: str, **values: Any) -> dict[str, Any]:
        current = self.connection.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM copy_types WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        quantity = int(values.get("quantity", 1))
        if current + quantity > 100:
            raise DomainError(
                "COPY_TYPE_TOTAL_EXCEEDED", "Project total quantity cannot exceed 100"
            )
        copy_type_id = new_id()
        self.connection.execute(
            "INSERT INTO copy_types(id,project_id,name,quantity,brief_text,use_reference_examples,use_description_requirements,description_requirements_json,must_include_json,must_avoid_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                copy_type_id,
                project_id,
                values["name"],
                quantity,
                values.get("brief_text", ""),
                int(values.get("use_reference_examples", False)),
                int(values.get("use_description_requirements", False)),
                _json(values.get("description_requirements", {})),
                _json(values.get("must_include", [])),
                _json(values.get("must_avoid", [])),
            ),
        )
        self.connection.commit()
        return self.get_copy_type(copy_type_id)

    def get_copy_type(self, copy_type_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM copy_types WHERE id=?", (copy_type_id,)
        ).fetchone()
        if not row:
            raise DomainError("COPY_TYPE_NOT_FOUND", "Copy type not found", status_code=404)
        return dict(row)

    def list_copy_types(self, project_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM copy_types WHERE project_id=? ORDER BY created_at", (project_id,)
            )
        ]

    def update_copy_type(self, copy_type_id: str, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "name",
            "quantity",
            "brief_text",
            "use_reference_examples",
            "use_description_requirements",
            "description_requirements_json",
            "must_include_json",
            "must_avoid_json",
            "style_profile_json",
            "style_profile_confirmed",
            "brief_review_json",
        }
        data = {key: value for key, value in values.items() if key in allowed}
        if "quantity" in data:
            current = self.get_copy_type(copy_type_id)
            other_total = self.connection.execute(
                "SELECT COALESCE(SUM(quantity),0) FROM copy_types WHERE project_id=? AND id<>?",
                (current["project_id"], copy_type_id),
            ).fetchone()[0]
            if other_total + int(data["quantity"]) > 100:
                raise DomainError(
                    "COPY_TYPE_TOTAL_EXCEEDED",
                    "Project total quantity cannot exceed 100",
                )
        for key in tuple(data):
            if key.endswith("_json") and not isinstance(data[key], str):
                data[key] = _json(data[key])
        if data:
            assignment = ",".join(f"{key}=?" for key in data)
            self.connection.execute(
                f"UPDATE copy_types SET {assignment},updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (*data.values(), copy_type_id),
            )  # noqa: S608
            self.connection.commit()
        return self.get_copy_type(copy_type_id)

    def delete_copy_type(self, copy_type_id: str) -> None:
        try:
            self.connection.execute("DELETE FROM copy_types WHERE id=?", (copy_type_id,))
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            raise DomainError(
                "COPY_TYPE_IN_USE", "Copy type has generated records", status_code=409
            ) from exc

    def add_reference(
        self, copy_type_id: str, raw_text: str, title: str, body: str, topics: list[str]
    ) -> dict[str, Any]:
        count = self.connection.execute(
            "SELECT COUNT(*) FROM reference_examples WHERE copy_type_id=?", (copy_type_id,)
        ).fetchone()[0]
        if count >= 5:
            raise DomainError(
                "REFERENCE_LIMIT_EXCEEDED", "At most five reference examples are allowed"
            )
        if not title.strip() or not body.strip():
            raise DomainError("REFERENCE_INCOMPLETE", "Reference title and body are required")
        reference_id = new_id()
        self.connection.execute(
            "INSERT INTO reference_examples(id,copy_type_id,ordinal,raw_text,title,body,topics_json) VALUES (?,?,?,?,?,?,?)",
            (reference_id, copy_type_id, count + 1, raw_text, title, body, _json(topics)),
        )
        self.connection.commit()
        return dict(
            self.connection.execute(
                "SELECT * FROM reference_examples WHERE id=?", (reference_id,)
            ).fetchone()
        )

    def list_references(self, copy_type_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM reference_examples WHERE copy_type_id=? ORDER BY ordinal",
                (copy_type_id,),
            )
        ]

    def create_rule(self, project_id: str, **values: Any) -> dict[str, Any]:
        rule_id = new_id()
        self.connection.execute(
            "INSERT INTO qc_rules(id,project_id,copy_type_id,scope,level,category,statement,source_evidence,source_kind,enabled) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                rule_id,
                project_id,
                values.get("copy_type_id"),
                values["scope"],
                values["level"],
                values["category"],
                values["statement"],
                values.get("source_evidence", ""),
                values.get("source_kind", "explicit"),
                int(values.get("enabled", True)),
            ),
        )
        self.connection.commit()
        return dict(
            self.connection.execute("SELECT * FROM qc_rules WHERE id=?", (rule_id,)).fetchone()
        )

    def list_rules(self, project_id: str, copy_type_id: str | None = None) -> list[dict[str, Any]]:
        if copy_type_id:
            rows = self.connection.execute(
                "SELECT * FROM qc_rules WHERE project_id=? AND (copy_type_id IS NULL OR copy_type_id=?) ORDER BY created_at",
                (project_id, copy_type_id),
            )
        else:
            rows = self.connection.execute(
                "SELECT * FROM qc_rules WHERE project_id=? ORDER BY created_at", (project_id,)
            )
        return [dict(row) for row in rows]

    def get_rule(self, rule_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM qc_rules WHERE id=?", (rule_id,)).fetchone()
        if not row:
            raise DomainError("QC_RULE_NOT_FOUND", "QC rule not found", status_code=404)
        return dict(row)

    def update_rule(self, rule_id: str, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {"level", "category", "statement", "source_evidence", "enabled"}
        data = {key: value for key, value in values.items() if key in allowed and value is not None}
        if data:
            assignments = ",".join(f"{key}=?" for key in data)
            self.connection.execute(
                f"UPDATE qc_rules SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (*data.values(), rule_id),
            )  # noqa: S608
            self.connection.commit()
        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: str) -> None:
        cursor = self.connection.execute("DELETE FROM qc_rules WHERE id=?", (rule_id,))
        self.connection.commit()
        if cursor.rowcount != 1:
            raise DomainError("QC_RULE_NOT_FOUND", "QC rule not found", status_code=404)

    def create_generation_run(
        self, project_id: str, requested_count: int, snapshot: Any, *, run_id: str | None = None
    ) -> dict[str, Any]:
        run_id = run_id or new_id()
        self.connection.execute(
            "INSERT INTO generation_runs(id,project_id,requested_count,configuration_snapshot_json) VALUES (?,?,?,?)",
            (run_id, project_id, requested_count, _json(snapshot)),
        )
        self.connection.commit()
        return dict(
            self.connection.execute(
                "SELECT * FROM generation_runs WHERE id=?", (run_id,)
            ).fetchone()
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM generation_runs WHERE id=?", (run_id,)
        ).fetchone()
        if not row:
            raise DomainError("RUN_NOT_FOUND", "Generation run not found", status_code=404)
        return dict(row)

    def create_item_slot(self, run_id: str, copy_type_id: str, ordinal: int) -> dict[str, Any]:
        item_id = new_id()
        try:
            self.connection.execute(
                "INSERT INTO copy_items(id,run_id,copy_type_id,ordinal) VALUES (?,?,?,?)",
                (item_id, run_id, copy_type_id, ordinal),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            raise DomainError(
                "ITEM_SLOT_DUPLICATE", "Item slot already exists", status_code=409
            ) from exc
        return self.get_item(item_id)

    def get_item(self, item_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM copy_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise DomainError("ITEM_NOT_FOUND", "Copy item not found", status_code=404)
        result = dict(row)
        version = self.connection.execute(
            "SELECT * FROM copy_item_versions WHERE item_id=? AND version=?",
            (item_id, result["current_version"]),
        ).fetchone()
        result["content"] = dict(version) if version else None
        return result

    def list_items(
        self, *, run_id: str | None = None, project_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT i.* FROM copy_items i"
        parameters: tuple[Any, ...] = ()
        if project_id:
            query += " JOIN generation_runs r ON r.id=i.run_id WHERE r.project_id=?"
            parameters = (project_id,)
        elif run_id:
            query += " WHERE i.run_id=?"
            parameters = (run_id,)
        query += " ORDER BY i.created_at,i.ordinal"
        return [self.get_item(row["id"]) for row in self.connection.execute(query, parameters)]

    def append_version(
        self,
        item_id: str,
        title: str,
        body: str,
        tags: list[str],
        origin: str,
        *,
        expected_version: int | None = None,
        change_note: str = "",
    ) -> dict[str, Any]:
        item = self.get_item(item_id)
        if expected_version is not None and item["current_version"] != expected_version:
            raise DomainError(
                "ITEM_VERSION_CONFLICT",
                "Item version changed",
                details={"current_version": item["current_version"]},
                status_code=409,
            )
        version = item["current_version"] + 1
        self.connection.execute(
            "INSERT INTO copy_item_versions(id,item_id,version,title,body,tags_json,origin,change_note) VALUES (?,?,?,?,?,?,?,?)",
            (new_id(), item_id, version, title, body, _json(tags), origin, change_note),
        )
        self.connection.execute(
            "UPDATE copy_items SET current_version=?,generation_status='generated',updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (version, item_id),
        )
        self.connection.commit()
        return self.get_item(item_id)

    def cas_item_state(
        self,
        item_id: str,
        expected: str,
        target: str,
        completion_reason: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        assignments = ["workflow_status=?", "completion_reason=?", "updated_at=CURRENT_TIMESTAMP"]
        values: list[Any] = [target, completion_reason]
        allowed = {"auto_rewrite_count", "generation_status", "error_code", "review_disposition"}
        for key, value in extra.items():
            if key in allowed:
                assignments.append(f"{key}=?")
                values.append(value)
        values.extend((item_id, expected))
        cursor = self.connection.execute(
            f"UPDATE copy_items SET {','.join(assignments)} WHERE id=? AND workflow_status=?",
            values,
        )  # noqa: S608
        if cursor.rowcount != 1:
            self.connection.rollback()
            raise DomainError("ITEM_STATE_CONFLICT", "Item state changed", status_code=409)
        self.connection.commit()
        return self.get_item(item_id)

    def create_qc_run(self, item_id: str, item_version: int, status: str = "running") -> str:
        qc_run_id = new_id()
        self.connection.execute(
            "INSERT INTO qc_runs(id,item_id,item_version,status) VALUES (?,?,?,?)",
            (qc_run_id, item_id, item_version, status),
        )
        self.connection.commit()
        return qc_run_id

    def add_findings(self, qc_run_id: str, item_id: str, findings: Iterable[Any]) -> None:
        for finding in findings:
            if hasattr(finding, "model_dump"):
                data = finding.model_dump()
            elif is_dataclass(finding):
                data = asdict(finding)
            else:
                data = dict(finding)
            self.connection.execute(
                "INSERT INTO qc_findings(id,qc_run_id,item_id,rule_id,level,category,message,evidence,suggestion,auto_fixable,source,matched_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    new_id(),
                    qc_run_id,
                    item_id,
                    data.get("rule_id"),
                    data.get("level", "soft"),
                    data["category"],
                    data["message"],
                    data.get("evidence", ""),
                    data.get("suggestion", ""),
                    int(data.get("auto_fixable", False)),
                    data.get("source", "deterministic"),
                    data.get("matched_id"),
                ),
            )
        self.connection.commit()

    def unresolved_findings(self, item_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM qc_findings WHERE item_id=? AND resolved=0 ORDER BY created_at",
                (item_id,),
            )
        ]

    @staticmethod
    def _finding_key(value: Any) -> tuple[str, str, str, str, str]:
        if hasattr(value, "model_dump"):
            data = value.model_dump()
        elif is_dataclass(value):
            data = asdict(value)
        else:
            data = dict(value)
        return (
            str(data.get("rule_id") or ""),
            str(data.get("category") or ""),
            str(data.get("source") or "deterministic"),
            str(data.get("matched_id") or ""),
            str(data.get("message") or ""),
        )

    def reconcile_findings(self, item_id: str, findings: Iterable[Any]) -> list[Any]:
        """Resolve only findings absent from a successful fresh QC evaluation."""
        fresh = list(findings)
        fresh_keys = {self._finding_key(finding) for finding in fresh}
        existing = self.unresolved_findings(item_id)
        existing_keys = {self._finding_key(finding) for finding in existing}
        resolved_ids = [
            finding["id"] for finding in existing if self._finding_key(finding) not in fresh_keys
        ]
        if resolved_ids:
            placeholders = ",".join("?" for _ in resolved_ids)
            self.connection.execute(
                f"UPDATE qc_findings SET resolved=1 WHERE id IN ({placeholders})",  # noqa: S608
                resolved_ids,
            )
            self.connection.commit()
        return [finding for finding in fresh if self._finding_key(finding) not in existing_keys]

    def set_item_error(self, item_id: str, error_code: str | None) -> None:
        self.connection.execute(
            "UPDATE copy_items SET error_code=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (error_code, item_id),
        )
        self.connection.commit()

    def add_review_event(
        self,
        item_id: str,
        action: str,
        reason: str = "",
        legacy_issues: list[str] | None = None,
        metadata: Any = None,
    ) -> str:
        event_id = new_id()
        self.connection.execute(
            "INSERT INTO review_events(id,item_id,action,reason,legacy_issues_json,metadata_json) VALUES (?,?,?,?,?,?)",
            (event_id, item_id, action, reason, _json(legacy_issues or []), _json(metadata or {})),
        )
        self.connection.commit()
        return event_id

    def create_export_run(
        self,
        export_id: str,
        project_id: str,
        sheet_title: str,
        generation_run_id: str | None = None,
    ) -> dict[str, Any]:
        self.connection.execute(
            "INSERT OR IGNORE INTO export_runs(id,project_id,generation_run_id,sheet_title) VALUES (?,?,?,?)",
            (export_id, project_id, generation_run_id, sheet_title),
        )
        self.connection.commit()
        return self.get_export_run(export_id)

    def get_export_run(self, export_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM export_runs WHERE id=?", (export_id,)
        ).fetchone()
        if not row:
            raise DomainError("EXPORT_RUN_NOT_FOUND", "Export run not found", status_code=404)
        return dict(row)

    def list_export_runs(self, project_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM export_runs WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            )
        ]

    def latest_review_event(self, item_id: str, action: str | None = None) -> dict[str, Any] | None:
        if action:
            row = self.connection.execute(
                "SELECT * FROM review_events WHERE item_id=? AND action=? ORDER BY created_at DESC LIMIT 1",
                (item_id, action),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT * FROM review_events WHERE item_id=? ORDER BY created_at DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_export_run(self, export_id: str, **values: Any) -> dict[str, Any]:
        allowed = {
            "sheet_id",
            "status",
            "row_count",
            "max_written_row",
            "payload_hash",
            "row_snapshot_json",
            "error_code",
        }
        data = {key: value for key, value in values.items() if key in allowed}
        if data:
            assignments = ",".join(f"{key}=?" for key in data)
            self.connection.execute(
                f"UPDATE export_runs SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (*data.values(), export_id),
            )  # noqa: S608
            self.connection.commit()
        return self.get_export_run(export_id)

    def log_model_call(
        self,
        operation: str,
        adapter: str,
        model: str,
        duration_ms: int,
        status: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error_code: str | None = None,
    ) -> None:
        self.connection.execute(
            "INSERT INTO model_call_logs(id,operation,adapter,model,duration_ms,status,input_tokens,output_tokens,error_code) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                operation,
                adapter,
                model,
                duration_ms,
                status,
                input_tokens,
                output_tokens,
                error_code,
            ),
        )
        self.connection.commit()
