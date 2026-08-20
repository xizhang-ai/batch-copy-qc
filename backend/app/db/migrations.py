from __future__ import annotations

import sqlite3
from pathlib import Path

from .connection import transaction

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.stem in applied:
            continue
        script = path.read_text(encoding="utf-8")
        with transaction(connection):
            for statement in script.split(";-- statement"):
                if statement.strip():
                    connection.execute(statement)
            connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (path.stem,))
