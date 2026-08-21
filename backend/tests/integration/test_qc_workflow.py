import pytest

from backend.app.domain.errors import DomainError
from backend.app.domain.schemas import CopyDraft, ModelQcFinding, SemanticQcResult
from backend.app.generation.service import GenerationService
from backend.app.model.fake import FakeModelAdapter
from backend.app.qc.service import QcService

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


class _InvalidTwiceThenPassModel(FakeModelAdapter):
    def __init__(self):
        self.calls = 0

    async def run_semantic_qc(self, context):
        self.calls += 1
        if self.calls < 3:
            raise DomainError(
                "MODEL_RESPONSE_INVALID",
                "invalid structured response",
                status_code=502,
            )
        return SemanticQcResult(findings=[], confidence=0.95)


@pytest.mark.asyncio
async def test_invalid_semantic_response_is_retried_before_human_review(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    repository.create_copy_type(project["id"], name="通勤", quantity=1, brief_text="真实体验")
    _run, items = GenerationService(repository).create_run(project["id"])
    repository.append_version(items[0]["id"], "测试标题", "测试正文", ["#测试"], "generation")
    model = _InvalidTwiceThenPassModel()

    result = await QcService(repository, model, retry_limit=2).run(items[0]["id"])

    assert model.calls == 3
    assert result["workflow_status"] == "completed"
    assert result["completion_reason"] == "ai_pass"


class _AlwaysInvalidModel(FakeModelAdapter):
    def __init__(self):
        self.calls = 0

    async def run_semantic_qc(self, context):
        self.calls += 1
        raise DomainError(
            "MODEL_RESPONSE_INVALID",
            "invalid structured response",
            status_code=502,
        )


@pytest.mark.asyncio
async def test_exhausted_invalid_semantic_response_preserves_content(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    repository.create_copy_type(project["id"], name="通勤", quantity=1, brief_text="真实体验")
    _run, items = GenerationService(repository).create_run(project["id"])
    repository.append_version(items[0]["id"], "测试标题", "测试正文", ["#测试"], "generation")
    model = _AlwaysInvalidModel()

    result = await QcService(repository, model, retry_limit=1).run(items[0]["id"])

    assert model.calls == 2
    assert result["workflow_status"] == "human_review"
    assert result["error_code"] == "MODEL_RESPONSE_INVALID"
    assert result["current_version"] == 1
    assert result["content"]["body"] == "测试正文"


def test_invalid_model_response_can_be_retried_from_item_api(client):
    project, _copy_type = _configured_project(client)
    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    settled = _wait_run(client, run["id"])
    item_id = settled["item_ids"][0]
    repository = client.app.state.repository
    repository.connection.execute(
        "UPDATE copy_items SET workflow_status='human_review',completion_reason=NULL,"
        "error_code='MODEL_RESPONSE_INVALID' WHERE id=?",
        (item_id,),
    )
    repository.connection.commit()

    retried = client.post(f"/api/items/{item_id}/qc:retry")

    assert retried.status_code == 200
    assert retried.json()["workflow_status"] == "completed"
    assert retried.json()["completion_reason"] == "ai_pass"


class _HardRuleFindingModel(FakeModelAdapter):
    def __init__(self, rule_id: str, *, auto_fixable: bool = True):
        self.rule_id = rule_id
        self.auto_fixable = auto_fixable

    async def run_semantic_qc(self, context):
        return SemanticQcResult(
            findings=[
                ModelQcFinding(
                    code="CLAIM_RISK",
                    message="命中项目硬规则",
                    rule_id=self.rule_id,
                    auto_fixable=self.auto_fixable,
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
    assert item["auto_rewrite_count"] == 4
    assert item["current_version"] == 5
    assert any(
        finding["rule_id"] == rule["id"] and finding["level"] == "hard"
        for finding in item["findings"]
    )


@pytest.mark.asyncio
async def test_persistent_content_finding_reaches_human_review_only_at_v5(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    repository.create_copy_type(project["id"], name="通勤", quantity=1, brief_text="真实体验")
    rule = repository.create_rule(
        project["id"],
        scope="project",
        level="hard",
        category="claim",
        statement="不得作治疗宣称",
    )
    _run, items = GenerationService(repository).create_run(project["id"])
    repository.append_version(
        items[0]["id"], "测试标题", "测试正文", ["#测试"], "generation"
    )
    service = QcService(
        repository,
        _HardRuleFindingModel(rule["id"], auto_fixable=False),
        auto_rewrite_limit=4,
    )

    rewritten = [await service.run(items[0]["id"]) for _ in range(4)]
    reviewed = await service.run(items[0]["id"])

    assert [item["current_version"] for item in rewritten] == [2, 3, 4, 5]
    assert all(item["workflow_status"] == "pending_ai_qc" for item in rewritten)
    assert reviewed["workflow_status"] == "human_review"
    assert reviewed["current_version"] == 5
    assert reviewed["auto_rewrite_count"] == 4


class _SimilarityRewriteModel(FakeModelAdapter):
    async def run_semantic_qc(self, context):
        return SemanticQcResult(
            findings=[
                ModelQcFinding(
                    code="SIMILARITY_TOO_HIGH",
                    message="模型重复报告相似度问题",
                    severity="error",
                    auto_fixable=False,
                )
            ]
            if context.similarity_context
            else [],
            confidence=0.95,
        )

    async def rewrite_copy(self, context):
        return CopyDraft(
            title="换一个完全不同的生活场景切入",
            body="从周末出行前的准备说起，重新组织信息顺序与表达方式。",
            tags=list(context.draft.tags),
        )


class _SimilarityAndIndependentHardModel(_SimilarityRewriteModel):
    def __init__(self, rule_id: str):
        self.rule_id = rule_id

    async def run_semantic_qc(self, context):
        return SemanticQcResult(
            findings=[
                ModelQcFinding(
                    code="SIMILARITY_TOO_HIGH",
                    message="模型重复报告相似度问题",
                    severity="error",
                    auto_fixable=False,
                ),
                ModelQcFinding(
                    code="SIMILARITY_POLICY_VIOLATION",
                    message="独立硬规则违规",
                    severity="error",
                    rule_id=self.rule_id,
                    auto_fixable=False,
                ),
            ],
            confidence=0.95,
        )


@pytest.mark.asyncio
async def test_batch_similarity_is_auto_rewritten_before_human_review(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    repository.create_copy_type(
        project["id"], name="通勤", quantity=2, brief_text="真实体验"
    )
    _run, items = GenerationService(repository).create_run(project["id"])
    for item in items:
        repository.append_version(
            item["id"],
            "完全相同的标题",
            "完全相同的正文内容，用于触发批次相似度检查。",
            ["#测试"],
            "generation",
        )
    repository.cas_item_state(items[0]["id"], "pending_ai_qc", "ai_qc_running")
    repository.cas_item_state(items[0]["id"], "ai_qc_running", "completed", "ai_pass")

    service = QcService(
        repository,
        _SimilarityRewriteModel(),
        auto_rewrite_limit=1,
        similarity_threshold=85,
    )
    rewritten = await service.run(items[1]["id"])

    assert rewritten["workflow_status"] == "pending_ai_qc"
    assert rewritten["auto_rewrite_count"] == 1
    assert rewritten["current_version"] == 2
    assert rewritten["content"]["title"] == "换一个完全不同的生活场景切入"
    assert len(
        [
            finding
            for finding in repository.unresolved_findings(items[1]["id"])
            if finding["category"] == "similarity"
        ]
    ) == 1

    completed = await service.run(items[1]["id"])
    assert completed["workflow_status"] == "completed"
    assert completed["completion_reason"] == "ai_pass"


@pytest.mark.asyncio
async def test_similarity_dedup_never_hides_an_independent_hard_rule(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"product": "气泡水"}, "confirmed": 1}
    )
    repository.create_copy_type(project["id"], name="通勤", quantity=2, brief_text="真实体验")
    rule = repository.create_rule(
        project["id"],
        scope="project",
        level="hard",
        category="policy",
        statement="不得违反独立硬规则",
    )
    _run, items = GenerationService(repository).create_run(project["id"])
    for item in items:
        repository.append_version(
            item["id"], "相同标题", "相同正文内容", ["#测试"], "generation"
        )
    repository.cas_item_state(items[0]["id"], "pending_ai_qc", "ai_qc_running")
    repository.cas_item_state(items[0]["id"], "ai_qc_running", "completed", "ai_pass")

    service = QcService(
        repository,
        _SimilarityAndIndependentHardModel(rule["id"]),
        auto_rewrite_limit=0,
        similarity_threshold=85,
    )
    result = await service.run(items[1]["id"])

    assert result["workflow_status"] == "human_review"
    unresolved = repository.unresolved_findings(items[1]["id"])
    assert len([row for row in unresolved if row["category"] == "similarity"]) == 1
    assert any(
        row["rule_id"] == rule["id"]
        and row["category"] == "SIMILARITY_POLICY_VIOLATION"
        and row["level"] == "hard"
        for row in unresolved
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
