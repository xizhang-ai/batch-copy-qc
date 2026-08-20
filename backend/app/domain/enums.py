from enum import StrEnum


class WorkflowStatus(StrEnum):
    PENDING_AI_QC = "pending_ai_qc"
    AI_QC_RUNNING = "ai_qc_running"
    AI_REWRITE_RUNNING = "ai_rewrite_running"
    HUMAN_REVIEW = "human_review"
    COMPLETED = "completed"


class CompletionReason(StrEnum):
    AI_PASS = "ai_pass"
    HUMAN_PASS = "human_pass"
    FORCED_PASS = "forced_pass"


class RuleLevel(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class RewriteOrigin(StrEnum):
    AUTO = "auto"
    HUMAN_SELECTION = "human_selection"
    HUMAN_EDIT = "human_edit"
    GENERATION = "generation"


class ReviewDisposition(StrEnum):
    OPEN = "open"
    REJECTED = "rejected"


class BriefScope(StrEnum):
    PROJECT = "project"
    COPY_TYPE = "copy_type"
