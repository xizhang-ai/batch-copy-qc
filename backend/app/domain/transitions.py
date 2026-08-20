from dataclasses import dataclass

from .enums import CompletionReason, WorkflowStatus
from .errors import DomainError


@dataclass(frozen=True, slots=True)
class TransitionResult:
    workflow_status: WorkflowStatus
    completion_reason: CompletionReason | None


_ALLOWED: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.PENDING_AI_QC: {
        WorkflowStatus.AI_QC_RUNNING,
        WorkflowStatus.HUMAN_REVIEW,
    },
    WorkflowStatus.AI_QC_RUNNING: {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.AI_REWRITE_RUNNING,
        WorkflowStatus.HUMAN_REVIEW,
    },
    WorkflowStatus.AI_REWRITE_RUNNING: {
        WorkflowStatus.PENDING_AI_QC,
        WorkflowStatus.HUMAN_REVIEW,
    },
    WorkflowStatus.HUMAN_REVIEW: {
        WorkflowStatus.HUMAN_REVIEW,
        WorkflowStatus.PENDING_AI_QC,
        WorkflowStatus.COMPLETED,
    },
    WorkflowStatus.COMPLETED: {WorkflowStatus.HUMAN_REVIEW},
}


def apply_transition(
    current: WorkflowStatus | str,
    target: WorkflowStatus | str,
    completion_reason: CompletionReason | str | None = None,
) -> TransitionResult:
    current_value = WorkflowStatus(current)
    target_value = WorkflowStatus(target)
    reason = CompletionReason(completion_reason) if completion_reason else None
    if target_value not in _ALLOWED[current_value]:
        raise DomainError(
            "ITEM_TRANSITION_INVALID",
            f"Cannot move item from {current_value} to {target_value}",
            details={"from": current_value, "to": target_value},
            status_code=409,
        )
    if target_value is WorkflowStatus.COMPLETED and reason is None:
        raise DomainError("COMPLETION_REASON_REQUIRED", "Completed items require a reason")
    if target_value is not WorkflowStatus.COMPLETED and reason is not None:
        raise DomainError(
            "COMPLETION_REASON_INVALID",
            "Only completed items can have a completion reason",
        )
    return TransitionResult(target_value, reason)
