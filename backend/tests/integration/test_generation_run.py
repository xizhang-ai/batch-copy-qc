import json
import time

import pytest

from backend.app.db.connection import connect
from backend.app.db.migrations import migrate
from backend.app.db.repositories import Repository
from backend.app.domain.errors import DomainError
from backend.app.generation.service import GenerationService
from backend.app.generation.worker import GenerationWorker
from backend.app.model.fake import FakeModelAdapter


def _configured_project(client, *, product="气泡水", quantity=1):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    client.patch(
        f"/api/projects/{project['id']}",
        json={"project_content": {"product": product}, "confirmed": True},
    )
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "通勤记录", "quantity": quantity, "brief_text": "真实体验"},
    ).json()
    return project, copy_type


def _wait_run(client, run_id, predicate=lambda run: run["pending"] == 0):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = client.get(f"/api/generation-runs/{run_id}").json()
        if predicate(result):
            return result
        time.sleep(0.01)
    raise AssertionError(f"run did not settle: {result}")


def test_generation_creates_stable_slots_and_versions(client):
    project, _copy_type = _configured_project(client, quantity=2)
    created = client.post(f"/api/projects/{project['id']}/generation-runs", json={})
    assert created.status_code == 201, created.text
    run = _wait_run(client, created.json()["id"])
    assert len(run["item_ids"]) == 2
    assert len(set(run["item_ids"])) == 2
    assert run["generated"] == 2


def test_batches_are_numbered_and_can_be_hidden_and_restored(client):
    project, _copy_type = _configured_project(client)
    first = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    _wait_run(client, first["id"])
    second = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    _wait_run(client, second["id"])

    runs = client.get(
        f"/api/projects/{project['id']}/generation-runs?include_archived=true"
    ).json()
    assert [(run["batch_number"], run["label"]) for run in runs] == [
        (2, "第 2 批"),
        (1, "第 1 批"),
    ]
    current = client.get(f"/api/projects/{project['id']}/board").json()
    assert current["run_id"] == second["id"]
    assert current["batch_number"] == 2
    assert len(current["items"]) == 1

    hidden = client.patch(
        f"/api/generation-runs/{second['id']}", json={"archived": True}
    )
    assert hidden.status_code == 200
    assert hidden.json()["archived"] is True
    fallback = client.get(f"/api/projects/{project['id']}/board").json()
    assert fallback["run_id"] == first["id"]
    assert fallback["batch_number"] == 1
    explicitly_hidden = client.get(
        f"/api/projects/{project['id']}/board?run_id={second['id']}"
    ).json()
    assert explicitly_hidden["run_id"] == second["id"]
    assert explicitly_hidden["run_archived"] is True

    restored = client.patch(
        f"/api/generation-runs/{second['id']}", json={"archived": False}
    )
    assert restored.status_code == 200
    assert restored.json()["archived"] is False
    assert client.get(f"/api/projects/{project['id']}/board").json()["run_id"] == second["id"]


def test_list_runs_returns_current_summary_instead_of_stale_generation_phase(client):
    project, copy_type = _configured_project(client)
    repository = client.app.state.repository
    run = repository.create_generation_run(project["id"], 1, {})
    item = repository.create_item_slot(run["id"], copy_type["id"], 1)
    repository.connection.execute(
        "UPDATE copy_items SET generation_status='failed',error_code='MODEL_RESPONSE_INVALID' WHERE id=?",
        (item["id"],),
    )
    repository.connection.commit()

    response = client.get(f"/api/projects/{project['id']}/generation-runs")

    assert response.status_code == 200
    listed = response.json()[0]
    assert listed["id"] == run["id"]
    assert listed["status"] == "failed"
    assert listed["generation_phase"] == "completed"


def test_generation_validation_returns_all_issues(client):
    project = client.post("/api/projects", json={"name": "empty"}).json()
    response = client.post(f"/api/projects/{project['id']}/generation-runs", json={})
    assert response.status_code == 400
    codes = {issue["code"] for issue in response.json()["error"]["details"]}
    assert {"PROJECT_NOT_CONFIRMED", "COPY_TYPE_REQUIRED", "PROJECT_FACTS_REQUIRED"} <= codes


def test_ui_finding_project_content_generates_short_ai_pass_copy(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    saved = client.patch(
        f"/api/projects/{project['id']}",
        json={
            "findings": [
                {
                    "id": "finding-product",
                    "section": "project_content",
                    "label": "产品",
                    "value": "清爽气泡水",
                    "evidence": "产品：清爽气泡水",
                    "confidence": "high",
                },
                {
                    "id": "finding-flavor",
                    "section": "project_content",
                    "label": "口味",
                    "value": "青柠味",
                    "evidence": "口味：青柠味",
                    "confidence": "high",
                },
            ],
            "confirmed": True,
        },
    )
    assert saved.status_code == 200
    client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "通勤记录", "quantity": 1, "brief_text": "真实体验"},
    )

    created = client.post(f"/api/projects/{project['id']}/generation-runs", json={})
    assert created.status_code == 201, created.text
    run = _wait_run(client, created.json()["id"])
    item = client.get(f"/api/items/{run['item_ids'][0]}").json()

    assert item["workflow_status"] == "completed"
    assert item["completion_reason"] == "ai_pass"
    assert len(item["title"]) <= 40
    assert "finding-product" not in item["title"]


def test_generation_snapshot_uses_effective_merged_rules(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    copy_type = repository.create_copy_type(
        project["id"], name="通勤", quantity=1, brief_text="真实体验"
    )
    repository.create_rule(
        project["id"],
        scope="project",
        level="soft",
        category="tone",
        statement="克制",
    )
    repository.create_rule(
        project["id"],
        copy_type_id=copy_type["id"],
        scope="copy_type",
        level="soft",
        category="tone",
        statement="活泼",
    )
    repository.create_rule(
        project["id"],
        scope="project",
        level="hard",
        category="claim",
        statement="不得宣称治疗",
    )

    run, _items = GenerationService(repository).create_run(project["id"])
    snapshot = json.loads(run["configuration_snapshot_json"])
    effective = {
        rule["category"]: rule["statement"] for rule in snapshot["copy_types"][0]["effective_rules"]
    }
    assert effective == {"tone": "活泼", "claim": "不得宣称治疗"}


def test_same_category_project_and_type_hard_rules_are_additive_and_do_not_block_run(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    copy_type = repository.create_copy_type(
        project["id"], name="通勤", quantity=1, brief_text="真实体验"
    )
    for statement in ("不得宣称治疗", "不得承诺见效"):
        repository.create_rule(
            project["id"],
            scope="project",
            level="hard",
            category="claim",
            statement=statement,
        )
    repository.create_rule(
        project["id"],
        copy_type_id=copy_type["id"],
        scope="copy_type",
        level="hard",
        category="claim",
        statement="不得虚构资质",
    )

    run, items = GenerationService(repository).create_run(project["id"])
    snapshot = json.loads(run["configuration_snapshot_json"])

    assert len(items) == 1
    assert snapshot["copy_types"][0]["rule_conflicts"] == []
    assert [rule["statement"] for rule in snapshot["copy_types"][0]["effective_rules"]] == [
        "不得宣称治疗",
        "不得承诺见效",
        "不得虚构资质",
    ]


def test_type_soft_override_attempt_against_project_hard_blocks_run(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    copy_type = repository.create_copy_type(
        project["id"], name="通勤", quantity=1, brief_text="真实体验"
    )
    repository.create_rule(
        project["id"],
        scope="project",
        level="hard",
        category="claim",
        statement="不得宣称治疗",
    )
    repository.create_rule(
        project["id"],
        copy_type_id=copy_type["id"],
        scope="copy_type",
        level="soft",
        category="claim",
        statement="突出治疗效果",
    )

    with pytest.raises(DomainError) as error:
        GenerationService(repository).create_run(project["id"])

    assert error.value.code == "GENERATION_VALIDATION_FAILED"
    assert any(issue["code"] == "HARD_RULE_CONFLICT" for issue in error.value.details)


class _RecoveryQc:
    auto_rewrite_limit = 1

    def __init__(self, repository):
        self.repository = repository
        self.calls: list[str] = []

    async def run(self, item_id):
        self.calls.append(item_id)
        return self.repository.cas_item_state(item_id, "pending_ai_qc", "completed", "ai_pass")


@pytest.mark.asyncio
async def test_worker_start_recovers_interrupted_qc_and_rewrite_states(tmp_path):
    connection = connect(tmp_path / "recovery.sqlite3")
    migrate(connection)
    repository = Repository(connection)
    project = repository.create_project("demo")
    copy_type = repository.create_copy_type(project["id"], name="通勤", quantity=2)
    run = repository.create_generation_run(project["id"], 2, {})
    qc_item = repository.create_item_slot(run["id"], copy_type["id"], 1)
    rewrite_item = repository.create_item_slot(run["id"], copy_type["id"], 2)
    empty_qc_item = repository.create_item_slot(run["id"], copy_type["id"], 3)
    empty_rewrite_item = repository.create_item_slot(run["id"], copy_type["id"], 4)
    for item in (qc_item, rewrite_item):
        repository.append_version(item["id"], "标题", "正文", ["#标签"], "generation")
    connection.execute(
        "UPDATE copy_items SET workflow_status='ai_qc_running' WHERE id=?", (qc_item["id"],)
    )
    connection.execute(
        "UPDATE copy_items SET workflow_status='ai_rewrite_running' WHERE id=?",
        (rewrite_item["id"],),
    )
    connection.execute(
        "UPDATE copy_items SET workflow_status='ai_qc_running' WHERE id=?",
        (empty_qc_item["id"],),
    )
    connection.execute(
        "UPDATE copy_items SET workflow_status='ai_rewrite_running' WHERE id=?",
        (empty_rewrite_item["id"],),
    )
    connection.commit()
    qc = _RecoveryQc(repository)
    worker = GenerationWorker(repository, FakeModelAdapter(), qc, concurrency=1)

    await worker.start()
    await worker.queue.join()
    await worker.stop()

    assert repository.get_item(qc_item["id"])["workflow_status"] == "completed"
    recovered_rewrite = repository.get_item(rewrite_item["id"])
    assert recovered_rewrite["workflow_status"] == "completed"
    assert recovered_rewrite["error_code"] is None
    assert set(qc.calls) == {qc_item["id"], rewrite_item["id"]}
    for empty_item in (empty_qc_item, empty_rewrite_item):
        recovered_empty = repository.get_item(empty_item["id"])
        assert recovered_empty["workflow_status"] == "human_review"
        assert recovered_empty["error_code"] == "WORKFLOW_RECOVERY_REQUIRED"
        assert recovered_empty["current_version"] == 0
