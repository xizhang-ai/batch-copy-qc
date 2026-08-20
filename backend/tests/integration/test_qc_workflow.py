from backend.app.domain.schemas import ModelQcFinding, SemanticQcResult
from backend.app.model.fake import FakeModelAdapter

from .test_generation_run import _configured_project, _wait_run


def test_ai_qc_pass_moves_directly_to_completed(client):
    project, _copy_type = _configured_project(client)
    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    settled = _wait_run(client, run["id"])
    item = client.get(f"/api/items/{settled['item_ids'][0]}").json()
    assert item["workflow_status"] == "completed"
    assert item["completion_reason"] == "ai_pass"


def test_auto_fix_rewrites_and_rechecks(client):
    project, _copy_type = _configured_project(client, product="[FAIL_QC] 气泡水")
    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    settled = _wait_run(client, run["id"])
    item = client.get(f"/api/items/{settled['item_ids'][0]}").json()
    assert item["workflow_status"] == "completed"
    assert item["current_version"] == 2
    assert "[FAIL_QC]" not in item["content"]["title"]


def test_low_confidence_moves_to_human_review(client):
    project, _copy_type = _configured_project(client, product="[LOW_CONFIDENCE] 气泡水")
    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    settled = _wait_run(client, run["id"])
    item = client.get(f"/api/items/{settled['item_ids'][0]}").json()
    assert item["workflow_status"] == "human_review"


class _HardRuleFindingModel(FakeModelAdapter):
    def __init__(self, rule_id: str):
        self.rule_id = rule_id

    async def run_semantic_qc(self, context):
        return SemanticQcResult(
            findings=[
                ModelQcFinding(
                    code="CLAIM_RISK",
                    message="命中项目硬规则",
                    rule_id=self.rule_id,
                    auto_fixable=True,
                )
            ],
            confidence=0.95,
        )


def test_model_finding_linked_to_hard_rule_stays_hard(client):
    project, _copy_type = _configured_project(client)
    rule = client.post(
        f"/api/projects/{project['id']}/qc-rules",
        json={
            "scope": "project",
            "level": "hard",
            "category": "claim",
            "statement": "不得作治疗宣称",
        },
    ).json()
    model = _HardRuleFindingModel(rule["id"])
    client.app.state.qc_service.model_adapter = model
    client.app.state.generation_worker.model_adapter = model
    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    settled = _wait_run(client, run["id"])
    item = client.get(f"/api/items/{settled['item_ids'][0]}").json()

    assert item["workflow_status"] == "human_review"
    assert any(
        finding["rule_id"] == rule["id"] and finding["level"] == "hard"
        for finding in item["findings"]
    )


class _UnlinkedErrorModel(FakeModelAdapter):
    def __init__(self):
        self.context = None

    async def run_semantic_qc(self, context):
        self.context = context
        return SemanticQcResult(
            findings=[
                ModelQcFinding(
                    code="UNKNOWN_HARD_VIOLATION",
                    message="阻断违规",
                    severity="error",
                )
            ],
            confidence=0.95,
        )


def test_semantic_qc_receives_rule_identity_and_unlinked_error_never_defaults_soft(client):
    project, _copy_type = _configured_project(client)
    rule = client.post(
        f"/api/projects/{project['id']}/qc-rules",
        json={
            "scope": "project",
            "level": "hard",
            "category": "claim",
            "statement": "不得作治疗宣称",
        },
    ).json()
    model = _UnlinkedErrorModel()
    client.app.state.qc_service.model_adapter = model
    client.app.state.generation_worker.model_adapter = model

    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    settled = _wait_run(client, run["id"])
    item = client.get(f"/api/items/{settled['item_ids'][0]}").json()

    assert model.context.rules[0].model_dump() == {
        "id": rule["id"],
        "level": "hard",
        "category": "claim",
        "requirement": "不得作治疗宣称",
    }
    finding = next(row for row in item["findings"] if row["category"] == "UNKNOWN_HARD_VIOLATION")
    assert finding["level"] == "hard"
