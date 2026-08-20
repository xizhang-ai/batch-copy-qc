import pytest

from backend.app.domain.enums import CompletionReason, WorkflowStatus
from backend.app.domain.errors import DomainError
from backend.app.domain.transitions import apply_transition


def test_ai_pass_completes_with_reason():
    result = apply_transition("ai_qc_running", "completed", "ai_pass")
    assert result.workflow_status is WorkflowStatus.COMPLETED
    assert result.completion_reason is CompletionReason.AI_PASS


def test_completed_requires_reason():
    with pytest.raises(DomainError, match="require a reason") as error:
        apply_transition("human_review", "completed")
    assert error.value.code == "COMPLETION_REASON_REQUIRED"


def test_recall_clears_reason():
    result = apply_transition("completed", "human_review")
    assert result.completion_reason is None


def test_illegal_transition_is_rejected():
    with pytest.raises(DomainError) as error:
        apply_transition("pending_ai_qc", "completed", "ai_pass")
    assert error.value.code == "ITEM_TRANSITION_INVALID"
