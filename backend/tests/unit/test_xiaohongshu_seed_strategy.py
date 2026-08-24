import json

import pytest

from backend.app.db.connection import connect
from backend.app.db.migrations import migrate
from backend.app.db.repositories import Repository
from backend.app.domain.schemas import CopyDraft
from backend.app.generation.service import GenerationService
from backend.app.generation.worker import GenerationWorker
from backend.app.generation.xiaohongshu_seed_strategy import (
    STRATEGY_NAME,
    STRATEGY_VERSION,
    build_instruction,
)


def test_strategy_has_a_stable_name_version_and_safe_generation_instruction():
    instruction = build_instruction()

    assert STRATEGY_NAME == "红书种草写作策略"
    assert STRATEGY_VERSION == "v1"
    assert "场景" in instruction
    assert "不得编造" in instruction
    assert "绝对化" in instruction


def test_generation_snapshot_freezes_strategy_name_and_version(repository):
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"产品": "清爽气泡水"}, "confirmed": 1}
    )
    repository.create_copy_type(
        project["id"],
        name="通勤",
        quantity=1,
        brief_text="自然分享",
        use_description_requirements=True,
        description_requirements={"tone": "自然分享"},
    )

    run, _items = GenerationService(repository).create_run(project["id"])
    snapshot = json.loads(run["configuration_snapshot_json"])

    assert snapshot["generation_strategy"] == {
        "name": "红书种草写作策略",
        "version": "v1",
    }


class _CaptureAdapter:
    def __init__(self) -> None:
        self.contexts = []

    async def generate_copy(self, context):
        self.contexts.append(context)
        return CopyDraft(title="通勤时的小发现", body="一个真实场景和产品细节。", tags=["#种草"])


class _PassQc:
    auto_rewrite_limit = 0

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    async def run(self, item_id: str):
        return self.repository.cas_item_state(item_id, "pending_ai_qc", "completed", "ai_pass")


@pytest.mark.asyncio
async def test_worker_injects_strategy_only_into_generation_context(tmp_path):
    connection = connect(tmp_path / "strategy.sqlite3")
    migrate(connection)
    repository = Repository(connection)
    project = repository.create_project("demo")
    repository.update_project(
        project["id"], {"project_content_json": {"产品": "清爽气泡水"}, "confirmed": 1}
    )
    repository.create_copy_type(
        project["id"],
        name="通勤",
        quantity=1,
        brief_text="自然分享",
        use_description_requirements=True,
        description_requirements={"tone": "自然分享"},
    )
    run, items = GenerationService(repository).create_run(project["id"])
    adapter = _CaptureAdapter()
    worker = GenerationWorker(repository, adapter, _PassQc(repository), concurrency=1)

    await worker.process(items[0]["id"])

    assert len(adapter.contexts) == 1
    requirements = adapter.contexts[0].description_requirements
    assert requirements[0].startswith("【红书种草写作策略 v1】")
    assert "自然分享" in requirements
    assert repository.get_item(items[0]["id"])["workflow_status"] == "completed"
    connection.close()
