import pytest
from pydantic import ValidationError

from backend.app.domain.schemas import AssistantAction, AssistantPlan, PreviewConfirmation


def test_unknown_assistant_action_is_rejected():
    with pytest.raises(ValidationError):
        AssistantAction(client_action_id="a1", kind="delete_database", payload={})


def test_empty_assistant_action_id_is_rejected():
    with pytest.raises(ValidationError):
        AssistantAction(client_action_id="", kind="set_project", payload={"name": "夏季种草"})


def test_assistant_plan_limits_blocking_questions():
    with pytest.raises(ValidationError):
        AssistantPlan(summary="需要补充信息", blockers=["a", "b", "c", "d"])


def test_preview_confirmation_accepts_three_items():
    assert PreviewConfirmation(expected_preview_item_count=3).expected_preview_item_count == 3
