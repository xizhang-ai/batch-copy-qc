export type WorkflowStatus =
  | "pending_ai_qc"
  | "ai_qc_running"
  | "ai_rewrite_running"
  | "human_review"
  | "completed";

export type CompletionReason = "ai_pass" | "human_pass" | "forced_pass";
export type Confidence = "high" | "medium" | "low";
export type BriefSection = "project_content" | "copy_requirements" | "qc_requirements" | "needs_confirmation";
export type RuleLevel = "hard" | "soft" | "pending";
export type RuleScope = "project" | "type";
export type ExportStatus = "pending" | "running" | "succeeded" | "failed";
export type GenerationMode = "preview" | "full";
export type GenerationPhase = "preview_running" | "awaiting_preview_approval" | "full_running" | "completed";

export interface Project {
  id: string;
  name: string;
  category: string;
  brand: string;
  status: "draft" | "confirmed" | "archived";
  updated_at: string;
  structured?: Record<string, unknown>;
}

export interface BriefFinding {
  id: string;
  section: BriefSection;
  label: string;
  value: string;
  evidence: string;
  confidence: Confidence;
}

export interface ParsedBrief {
  source_name: string;
  findings: BriefFinding[];
}

export interface ReferenceExample {
  id: string;
  title: string;
  body: string;
  topics: string[];
  raw_text: string;
}

export interface ReferenceProfile {
  title_hook: string;
  structure_rhythm: string;
  point_of_view: string;
  tone: string;
  persona: string;
  scenario: string;
  information_density: string;
  ending: string;
  topic_strategy: string;
  source_facts: string[];
  avoid_expressions: string[];
  confirmed: boolean;
}

export type TypeBriefReviewDecision = "pending" | "confirmed" | "ignored";

export interface TypeBriefReviewItem {
  id: string;
  section: string;
  value: string;
  source_quote: string;
  confidence: number;
  decision: TypeBriefReviewDecision;
}

export interface TypeBriefReview {
  project_change_suggestions: TypeBriefReviewItem[];
  conflicts: TypeBriefReviewItem[];
}

export interface ParsedTypeBrief extends Partial<CopyType> {
  parsed_finding_count?: number;
  project_change_suggestions?: Array<Partial<TypeBriefReviewItem>>;
  conflicts?: Array<Partial<TypeBriefReviewItem>>;
}

export interface CopyType {
  id: string;
  project_id: string;
  name: string;
  quantity: number;
  sources: Array<"manual" | "brief" | "reference">;
  input_modes: Array<"reference_examples" | "description_requirements">;
  type_brief: string;
  requirements: {
    title_direction: string;
    body_structure: string;
    tone: string;
    persona: string;
    scenario: string;
    topic_requirements: string;
  };
  must_include: string[];
  must_avoid: string[];
  references: ReferenceExample[];
  reference_profile?: ReferenceProfile;
  brief_review?: TypeBriefReview;
}

export interface ClassifiedTypeFile {
  id: string;
  filename: string;
  suggested_type: string;
  evidence: string;
  confidence: Confidence;
  assigned_type_id?: string | null;
}

export interface QcRule {
  id: string;
  project_id: string;
  copy_type_id?: string;
  scope: RuleScope;
  level: RuleLevel;
  category: "claim" | "fact" | "style" | "structure" | "similarity" | "other";
  statement: string;
  source_kind: "explicit_project_qc" | "explicit_type_qc" | "derived_type_constraint";
  source_evidence: string;
  enabled: boolean;
  conflict?: string;
}

export interface QcFinding {
  id: string;
  level: "hard" | "soft";
  category: string;
  status: "open" | "resolved";
  message: string;
  evidence: string;
  suggestion: string;
  field?: "title" | "body" | "tags";
  auto_fixable: boolean;
  confidence?: number;
  source?: "deterministic" | "model" | "system" | "similarity";
}

export interface CopyItem {
  id: string;
  copy_type_id: string;
  copy_type_name: string;
  ordinal: number;
  title: string;
  body: string;
  tags: string[];
  workflow_status: WorkflowStatus;
  completion_reason?: CompletionReason;
  review_disposition?: "open" | "rejected";
  version: number;
  auto_rewrite_count: number;
  similarity_score?: number;
  progress?: string;
  findings: QcFinding[];
  updated_at: string;
}

export type ItemResponse = Partial<CopyItem> & Pick<CopyItem, "id">;

export interface BoardData {
  project_id: string;
  run_id: string;
  batch_number?: number;
  run_archived: boolean;
  run_status: "idle" | "running" | "completed";
  items: CopyItem[];
  updated_at: string;
}

export interface GenerationRun {
  id: string;
  project_id: string;
  status: "queued" | "pending" | "running" | "completed" | "partial_failed" | "failed";
  total_requested: number;
  batch_number: number;
  label: string;
  archived: boolean;
  archived_at?: string;
  created_at: string;
  generation_mode?: GenerationMode;
  generation_phase?: GenerationPhase;
  preview_item_count?: number;
}

export interface AssistantAction {
  client_action_id: string;
  kind: "set_project" | "replace_project_findings" | "upsert_copy_type" | "replace_project_rules" | "start_generation";
  payload: Record<string, unknown>;
}

export interface AssistantPlan {
  summary: string;
  blockers: string[];
  assumptions: string[];
  actions: AssistantAction[];
}

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  plan?: AssistantPlan | null;
  created_at: string;
}

export interface AssistantSession {
  id: string;
  project_id: string;
  messages: AssistantMessage[];
}

export interface ConnectionStatus {
  model: { configured: boolean; adapter: string; model?: string };
  feishu: { configured: boolean; adapter: string; target?: string };
}

export interface ExportPreview {
  completed: number;
  by_reason: Record<CompletionReason, number>;
  excluded_human_review: number;
  excluded_rejected: number;
  columns: string[];
}

export interface ExportRun {
  id: string;
  project_id: string;
  generation_run_id: string;
  status: ExportStatus;
  sheet_id?: string;
  sheet_title: string;
  row_count: number;
  adapter: "fake" | "feishu";
  safe_error?: string;
  created_at: string;
}

export interface ApiErrorShape {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export interface ReviewPayload {
  action: "reject" | "pass" | "force_pass" | "recall";
  reason?: string;
  legacy_issues?: string[];
}

export interface RewriteSelectionPayload {
  expected_version: number;
  selected_text: string;
  selection_start: number;
  selection_end: number;
  field: "title" | "body";
  instruction: string;
}
