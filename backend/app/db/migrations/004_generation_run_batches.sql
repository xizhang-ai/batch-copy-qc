ALTER TABLE generation_runs ADD COLUMN batch_number INTEGER NOT NULL DEFAULT 0;-- statement
ALTER TABLE generation_runs ADD COLUMN archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1));-- statement
ALTER TABLE generation_runs ADD COLUMN archived_at TEXT;-- statement
UPDATE generation_runs AS current_run
SET batch_number = (
    SELECT COUNT(*)
    FROM generation_runs AS candidate
    WHERE candidate.project_id = current_run.project_id
      AND (
        candidate.created_at < current_run.created_at
        OR (candidate.created_at = current_run.created_at AND candidate.rowid <= current_run.rowid)
      )
);-- statement
CREATE UNIQUE INDEX idx_generation_runs_project_batch_unique
ON generation_runs(project_id, batch_number);-- statement
CREATE INDEX idx_generation_runs_project_batch
ON generation_runs(project_id, archived, batch_number DESC);-- statement
