from backend.app.domain.errors import DomainError
from backend.app.model.fake import FakeModelAdapter

from .test_generation_run import _configured_project, _wait_run


def _human_item(client):
    project, _copy_type = _configured_project(client)
    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    settled = _wait_run(client, run["id"])
    item_id = settled["item_ids"][0]
    response = client.post(f"/api/items/{item_id}/review", json={"action": "recall"})
    assert response.status_code == 200, response.text
    return project, item_id, response.json()


def test_direct_edit_and_selection_rewrite_stay_in_human_review(client):
    _project, item_id, item = _human_item(client)
    content = item["content"]
    edited = client.patch(
        f"/api/items/{item_id}",
        json={
            "expected_version": item["current_version"],
            "title": content["title"],
            "body": content["body"] + "\n人工补充",
            "tags": content["tags"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["workflow_status"] == "human_review"
    assert edited.json()["copy_type_name"] == "通勤记录"
    assert isinstance(edited.json()["findings"], list)
    assert edited.json()["findings"] == client.get(f"/api/items/{item_id}").json()["findings"]
    body = edited.json()["content"]["body"]
    selected = "人工补充"
    start = body.index(selected)
    rewritten = client.post(
        f"/api/items/{item_id}/rewrite-selection",
        json={
            "expected_version": edited.json()["current_version"],
            "field": "body",
            "selection_start": start,
            "selection_end": start + len(selected),
            "selected_text": selected,
            "instruction": "更自然",
        },
    )
    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()["workflow_status"] == "human_review"
    assert rewritten.json()["copy_type_name"] == "通勤记录"
    assert isinstance(rewritten.json()["findings"], list)
    assert rewritten.json()["findings"] == client.get(f"/api/items/{item_id}").json()["findings"]


def test_force_pass_requires_legacy_issues(client):
    _project, item_id, _item = _human_item(client)
    response = client.post(
        f"/api/items/{item_id}/review", json={"action": "force_pass", "legacy_issues": []}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FORCE_PASS_ISSUES_REQUIRED"


def test_force_pass_rejects_blank_issue_elements_and_requires_reason(client):
    _project, item_id, _item = _human_item(client)
    blank = client.post(
        f"/api/items/{item_id}/review",
        json={"action": "force_pass", "reason": "例外", "legacy_issues": ["   "]},
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"

    no_reason = client.post(
        f"/api/items/{item_id}/review",
        json={"action": "force_pass", "reason": "   ", "legacy_issues": ["保留问题"]},
    )
    assert no_reason.status_code == 400
    assert no_reason.json()["error"]["code"] == "FORCE_PASS_REASON_REQUIRED"


def test_normal_pass_and_recall(client):
    _project, item_id, _item = _human_item(client)
    passed = client.post(f"/api/items/{item_id}/review", json={"action": "pass"})
    assert passed.status_code == 200, passed.text
    assert passed.json()["completion_reason"] == "human_pass"
    recalled = client.post(f"/api/items/{item_id}/review", json={"action": "recall"})
    assert recalled.json()["workflow_status"] == "human_review"
    assert recalled.json()["completion_reason"] is None


def test_human_edit_resolves_a_similarity_finding_when_fresh_qc_no_longer_matches(client):
    _project, item_id, item = _human_item(client)
    repository = client.app.state.repository
    qc_run_id = repository.create_qc_run(item_id, item["current_version"], "completed")
    repository.add_findings(
        qc_run_id,
        item_id,
        [
            {
                "level": "hard",
                "category": "similarity",
                "message": "与另一条文案过于相似",
                "evidence": "score=96",
                "auto_fixable": False,
                "source": "similarity",
            }
        ],
    )
    content = item["content"]
    edited = client.patch(
        f"/api/items/{item_id}",
        json={
            "expected_version": item["current_version"],
            "title": content["title"] + "调整",
            "body": content["body"],
            "tags": content["tags"],
        },
    )

    assert edited.status_code == 200
    unresolved = repository.unresolved_findings(item_id)
    assert not any(row["category"] == "similarity" for row in unresolved)
    passed = client.post(f"/api/items/{item_id}/review", json={"action": "pass"})
    assert passed.status_code == 200
    assert passed.json()["completion_reason"] == "human_pass"


class _UnavailableReviewQc(FakeModelAdapter):
    async def run_semantic_qc(self, context):
        raise DomainError("MODEL_UNAVAILABLE", "down", status_code=503)


def test_failed_human_recheck_keeps_old_findings_and_blocks_normal_pass(client):
    _project, item_id, item = _human_item(client)
    repository = client.app.state.repository
    qc_run_id = repository.create_qc_run(item_id, item["current_version"], "completed")
    repository.add_findings(
        qc_run_id,
        item_id,
        [
            {
                "level": "hard",
                "category": "claim",
                "message": "旧的语义硬问题",
                "source": "semantic",
            }
        ],
    )
    client.app.state.qc_service.model_adapter = _UnavailableReviewQc()
    client.app.state.qc_service.retry_limit = 0
    content = item["content"]
    edited = client.patch(
        f"/api/items/{item_id}",
        json={
            "expected_version": item["current_version"],
            "title": content["title"] + "已改",
            "body": content["body"],
            "tags": content["tags"],
        },
    )
    assert edited.status_code == 200
    unresolved = repository.unresolved_findings(item_id)
    assert any(row["message"] == "旧的语义硬问题" for row in unresolved)
    assert any(row["source"] == "system" for row in unresolved)

    passed = client.post(f"/api/items/{item_id}/review", json={"action": "pass"})
    assert passed.status_code == 409
    assert passed.json()["error"]["code"] == "QC_RECHECK_INCOMPLETE"
