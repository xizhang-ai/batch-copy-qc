import json
import sqlite3
from types import SimpleNamespace

import pytest

from backend.app.api.dependencies import get_repository
from backend.app.db.connection import connect
from backend.app.db.migrations import migrate
from backend.app.db.repositories import Repository
from backend.app.domain.errors import DomainError


def test_migrations_are_idempotent(tmp_path):
    connection = connect(tmp_path / "db.sqlite3")
    migrate(connection)
    migrate(connection)
    names = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"projects", "copy_items", "model_call_logs", "export_runs"} <= names


def test_request_repository_dependency_closes_its_connection(tmp_path):
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(database_path=tmp_path / "request.sqlite3")
            )
        )
    )
    dependency = get_repository(request)
    repository = next(dependency)
    connection = repository.connection

    dependency.close()

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_export_idempotency_migration_upgrades_existing_001_database(tmp_path):
    connection = connect(tmp_path / "legacy.sqlite3")
    connection.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO schema_migrations(version) VALUES ('001_initial');
        CREATE TABLE copy_types (
            id TEXT PRIMARY KEY
        );
        CREATE TABLE export_runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            generation_run_id TEXT,
            sheet_title TEXT NOT NULL,
            sheet_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            row_count INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO export_runs(id, project_id, sheet_title) VALUES ('legacy', 'p1', '旧数据');
        """
    )
    migrate(connection)

    columns = {row[1] for row in connection.execute("PRAGMA table_info(export_runs)")}
    assert {"max_written_row", "payload_hash", "row_snapshot_json"} <= columns
    row = connection.execute("SELECT * FROM export_runs WHERE id='legacy'").fetchone()
    assert row["sheet_title"] == "旧数据"
    assert row["max_written_row"] == 0


def test_brief_review_migration_preserves_legacy_copy_type_rows(tmp_path):
    connection = connect(tmp_path / "legacy-copy-types.sqlite3")
    connection.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO schema_migrations(version) VALUES ('001_initial');
        INSERT INTO schema_migrations(version) VALUES ('002_export_idempotency');
        CREATE TABLE copy_types (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        INSERT INTO copy_types(id, name) VALUES ('legacy-type', '旧类型');
        """
    )

    migrate(connection)

    row = connection.execute("SELECT * FROM copy_types WHERE id='legacy-type'").fetchone()
    assert row["name"] == "旧类型"
    assert json.loads(row["brief_review_json"]) == {
        "project_change_suggestions": [],
        "conflicts": [],
    }
    versions = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    assert "003_copy_type_brief_review" in versions


def test_duplicate_item_slot_is_rejected(tmp_path):
    connection = connect(tmp_path / "db.sqlite3")
    migrate(connection)
    repository = Repository(connection)
    project = repository.create_project("demo")
    copy_type = repository.create_copy_type(project["id"], name="通勤", quantity=1)
    run = repository.create_generation_run(project["id"], 1, {})
    repository.create_item_slot(run["id"], copy_type["id"], 1)
    with pytest.raises(DomainError) as error:
        repository.create_item_slot(run["id"], copy_type["id"], 1)
    assert error.value.code == "ITEM_SLOT_DUPLICATE"


def test_completed_constraint_requires_reason(tmp_path):
    connection = connect(tmp_path / "db.sqlite3")
    migrate(connection)
    repository = Repository(connection)
    project = repository.create_project("demo")
    copy_type = repository.create_copy_type(project["id"], name="通勤", quantity=1)
    run = repository.create_generation_run(project["id"], 1, {})
    item = repository.create_item_slot(run["id"], copy_type["id"], 1)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE copy_items SET workflow_status='completed' WHERE id=?", (item["id"],)
        )


def test_auto_rewrite_version_and_counter_roll_back_together(tmp_path):
    connection = connect(tmp_path / "atomic-rewrite.sqlite3")
    migrate(connection)
    repository = Repository(connection)
    project = repository.create_project("demo")
    copy_type = repository.create_copy_type(project["id"], name="通勤", quantity=1)
    run = repository.create_generation_run(project["id"], 1, {})
    item = repository.create_item_slot(run["id"], copy_type["id"], 1)
    repository.append_version(item["id"], "标题", "正文", ["#标签"], "generation")
    repository.cas_item_state(item["id"], "pending_ai_qc", "ai_qc_running")
    repository.cas_item_state(item["id"], "ai_qc_running", "ai_rewrite_running")
    connection.executescript(
        """
        CREATE TRIGGER fail_auto_rewrite_transition
        BEFORE UPDATE ON copy_items
        WHEN OLD.workflow_status='ai_rewrite_running'
          AND NEW.workflow_status='pending_ai_qc'
        BEGIN
          SELECT RAISE(ABORT, 'simulated crash window');
        END;
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.append_auto_rewrite(
            item["id"],
            "改写标题",
            "改写正文",
            ["#改写"],
            expected_version=1,
            expected_rewrite_count=0,
        )

    unchanged = repository.get_item(item["id"])
    assert unchanged["workflow_status"] == "ai_rewrite_running"
    assert unchanged["current_version"] == 1
    assert unchanged["auto_rewrite_count"] == 0
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM copy_item_versions WHERE item_id=?", (item["id"],)
        ).fetchone()[0]
        == 1
    )
