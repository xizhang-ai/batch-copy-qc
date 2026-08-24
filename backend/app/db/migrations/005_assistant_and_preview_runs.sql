ALTER TABLE generation_runs ADD COLUMN generation_mode TEXT NOT NULL DEFAULT 'full' CHECK(generation_mode IN ('preview','full'));-- statement
ALTER TABLE generation_runs ADD COLUMN generation_phase TEXT NOT NULL DEFAULT 'full_running' CHECK(generation_phase IN ('preview_running','awaiting_preview_approval','full_running','completed'));-- statement
ALTER TABLE generation_runs ADD COLUMN preview_item_count INTEGER NOT NULL DEFAULT 0 CHECK(preview_item_count BETWEEN 0 AND 3);-- statement
ALTER TABLE generation_runs ADD COLUMN preview_confirmed_at TEXT;-- statement
CREATE TABLE assistant_sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id)
);-- statement
CREATE TABLE assistant_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    plan_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE assistant_action_receipts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
    client_action_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, client_action_id)
);-- statement
CREATE INDEX idx_assistant_messages_session_created ON assistant_messages(session_id, created_at);
