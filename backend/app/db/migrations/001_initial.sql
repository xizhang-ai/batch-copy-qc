CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    brand TEXT NOT NULL DEFAULT '',
    product_sku TEXT NOT NULL DEFAULT '',
    project_content_json TEXT NOT NULL DEFAULT '{}',
    copy_requirements_json TEXT NOT NULL DEFAULT '{}',
    qc_requirements_json TEXT NOT NULL DEFAULT '{}',
    pending_confirmation_json TEXT NOT NULL DEFAULT '[]',
    confirmed INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE brief_sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    copy_type_id TEXT,
    source_kind TEXT NOT NULL,
    display_name TEXT NOT NULL,
    stored_name TEXT,
    raw_text TEXT NOT NULL DEFAULT '',
    parsed_json TEXT,
    parse_status TEXT NOT NULL DEFAULT 'pending' CHECK(parse_status IN ('pending','parsed','failed')),
    error_code TEXT,
    classification_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE copy_types (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 100),
    brief_text TEXT NOT NULL DEFAULT '',
    use_reference_examples INTEGER NOT NULL DEFAULT 0 CHECK(use_reference_examples IN (0,1)),
    use_description_requirements INTEGER NOT NULL DEFAULT 0 CHECK(use_description_requirements IN (0,1)),
    description_requirements_json TEXT NOT NULL DEFAULT '{}',
    must_include_json TEXT NOT NULL DEFAULT '[]',
    must_avoid_json TEXT NOT NULL DEFAULT '[]',
    style_profile_json TEXT,
    style_profile_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(style_profile_confirmed IN (0,1)),
    template_id TEXT,
    template_version TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name)
);-- statement
CREATE TABLE reference_examples (
    id TEXT PRIMARY KEY,
    copy_type_id TEXT NOT NULL REFERENCES copy_types(id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 5),
    raw_text TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    topics_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(copy_type_id, ordinal)
);-- statement
CREATE TABLE qc_rules (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    copy_type_id TEXT REFERENCES copy_types(id) ON DELETE RESTRICT,
    scope TEXT NOT NULL CHECK(scope IN ('project','copy_type')),
    level TEXT NOT NULL CHECK(level IN ('hard','soft')),
    category TEXT NOT NULL,
    statement TEXT NOT NULL,
    source_evidence TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL DEFAULT 'explicit',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK((scope='project' AND copy_type_id IS NULL) OR (scope='copy_type' AND copy_type_id IS NOT NULL))
);-- statement
CREATE TABLE generation_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','completed','partial_failed','failed')),
    requested_count INTEGER NOT NULL,
    configuration_snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE copy_items (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES generation_runs(id) ON DELETE RESTRICT,
    copy_type_id TEXT NOT NULL REFERENCES copy_types(id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL,
    workflow_status TEXT NOT NULL DEFAULT 'pending_ai_qc' CHECK(workflow_status IN ('pending_ai_qc','ai_qc_running','ai_rewrite_running','human_review','completed')),
    completion_reason TEXT CHECK(completion_reason IN ('ai_pass','human_pass','forced_pass')),
    current_version INTEGER NOT NULL DEFAULT 0,
    auto_rewrite_count INTEGER NOT NULL DEFAULT 0,
    generation_status TEXT NOT NULL DEFAULT 'queued' CHECK(generation_status IN ('queued','running','generated','failed')),
    error_code TEXT,
    review_disposition TEXT NOT NULL DEFAULT 'open' CHECK(review_disposition IN ('open','rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, copy_type_id, ordinal),
    CHECK((workflow_status='completed' AND completion_reason IS NOT NULL) OR (workflow_status<>'completed' AND completion_reason IS NULL))
);-- statement
CREATE TABLE copy_item_versions (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES copy_items(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK(version > 0),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    origin TEXT NOT NULL,
    change_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(item_id, version)
);-- statement
CREATE TABLE qc_runs (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES copy_items(id) ON DELETE RESTRICT,
    item_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);-- statement
CREATE TABLE qc_findings (
    id TEXT PRIMARY KEY,
    qc_run_id TEXT NOT NULL REFERENCES qc_runs(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES copy_items(id) ON DELETE RESTRICT,
    rule_id TEXT,
    level TEXT NOT NULL CHECK(level IN ('hard','soft')),
    category TEXT NOT NULL,
    message TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '',
    suggestion TEXT NOT NULL DEFAULT '',
    auto_fixable INTEGER NOT NULL DEFAULT 0 CHECK(auto_fixable IN (0,1)),
    resolved INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN (0,1)),
    source TEXT NOT NULL,
    matched_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE rewrite_requests (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES copy_items(id) ON DELETE RESTRICT,
    expected_version INTEGER NOT NULL,
    origin TEXT NOT NULL,
    request_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE review_events (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES copy_items(id) ON DELETE RESTRICT,
    action TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    legacy_issues_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE export_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    generation_run_id TEXT REFERENCES generation_runs(id) ON DELETE RESTRICT,
    sheet_title TEXT NOT NULL,
    sheet_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','succeeded','failed')),
    row_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);-- statement
CREATE TABLE model_call_logs (
    id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    adapter TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
