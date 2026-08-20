ALTER TABLE export_runs ADD COLUMN max_written_row INTEGER NOT NULL DEFAULT 0;-- statement
ALTER TABLE export_runs ADD COLUMN payload_hash TEXT;-- statement
ALTER TABLE export_runs ADD COLUMN row_snapshot_json TEXT;-- statement
