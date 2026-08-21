from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

from ..db.repositories import Repository
from ..domain.schemas import GenerationContext, ReferenceExample, ReferenceStyleProfile
from .service import normalize_project_facts


class GenerationWorker:
    def __init__(
        self, repository: Repository, model_adapter: Any, qc_service: Any, concurrency: int = 2
    ) -> None:
        self.repository = repository
        self.model_adapter = model_adapter
        self.qc_service = qc_service
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.concurrency = concurrency
        self.tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if self.tasks:
            return
        self.repository.connection.execute(
            "UPDATE copy_items SET generation_status="
            "CASE WHEN current_version>0 THEN 'generated' ELSE 'queued' END "
            "WHERE generation_status='running'"
        )
        self.repository.connection.execute(
            "UPDATE copy_items SET workflow_status='pending_ai_qc',error_code=NULL "
            "WHERE workflow_status='ai_qc_running' AND generation_status='generated'"
        )
        self.repository.connection.execute(
            "UPDATE copy_items SET workflow_status='human_review',"
            "error_code='WORKFLOW_RECOVERY_REQUIRED' "
            "WHERE workflow_status='ai_qc_running' AND generation_status<>'generated'"
        )
        self.repository.connection.execute(
            "UPDATE copy_items SET workflow_status='pending_ai_qc',error_code=NULL "
            "WHERE workflow_status='ai_rewrite_running' AND generation_status='generated'"
        )
        self.repository.connection.execute(
            "UPDATE copy_items SET workflow_status='human_review',"
            "error_code='WORKFLOW_RECOVERY_REQUIRED' "
            "WHERE workflow_status='ai_rewrite_running' AND generation_status<>'generated'"
        )
        self.repository.connection.commit()
        for row in self.repository.connection.execute(
            "SELECT id FROM copy_items WHERE workflow_status='pending_ai_qc' "
            "AND generation_status IN ('queued','generated')"
        ):
            await self.queue.put(row["id"])
        self.tasks = [asyncio.create_task(self._run()) for _ in range(self.concurrency)]

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with suppress(asyncio.CancelledError):
                await task
        self.tasks.clear()

    async def enqueue(self, item_id: str) -> None:
        await self.queue.put(item_id)

    async def _run(self) -> None:
        while True:
            item_id = await self.queue.get()
            try:
                await self.process(item_id)
            finally:
                self.queue.task_done()

    async def process(self, item_id: str) -> None:
        item = self.repository.get_item(item_id)
        if item["workflow_status"] != "pending_ai_qc":
            return
        if item["generation_status"] == "generated":
            await self._run_qc(item_id)
            return
        self.repository.connection.execute(
            "UPDATE copy_items SET generation_status='running',error_code=NULL WHERE id=?",
            (item_id,),
        )
        self.repository.connection.commit()
        try:
            run = self.repository.get_run(item["run_id"])
            snapshot = json.loads(run["configuration_snapshot_json"])
            copy_type = next(
                row for row in snapshot["copy_types"] if row["id"] == item["copy_type_id"]
            )
            project = snapshot["project"]
            profile_raw = (
                json.loads(copy_type["style_profile_json"])
                if copy_type.get("style_profile_json")
                else None
            )
            context = GenerationContext(
                project_facts=normalize_project_facts(json.loads(project["project_content_json"])),
                reference_examples=[
                    ReferenceExample(
                        raw_text=row["raw_text"],
                        title=row["title"],
                        body=row["body"],
                        topics=json.loads(row["topics_json"]),
                    )
                    for row in copy_type["reference_examples"]
                ],
                style_profile=ReferenceStyleProfile.model_validate(profile_raw)
                if profile_raw
                else None,
                description_requirements=list(
                    json.loads(copy_type["description_requirements_json"]).values()
                ),
                must_include=json.loads(copy_type["must_include_json"]),
                must_avoid=json.loads(copy_type["must_avoid_json"]),
                effective_rules=[rule["statement"] for rule in copy_type["effective_rules"]],
                slot_id=item_id,
                idempotency_key=f"generation:{item_id}",
            )
            draft = await self.model_adapter.generate_copy(context)
            self.repository.append_version(
                item_id, draft.title, draft.body, draft.tags, "generation"
            )
            await self._run_qc(item_id)
        except Exception as exc:
            code = getattr(exc, "code", "GENERATION_FAILED")
            self.repository.connection.execute(
                "UPDATE copy_items SET generation_status='failed',error_code=?,workflow_status='human_review' WHERE id=?",
                (code, item_id),
            )
            self.repository.connection.commit()

    async def _run_qc(self, item_id: str) -> None:
        for _attempt in range(self.qc_service.auto_rewrite_limit + 2):
            result = await self.qc_service.run(item_id)
            if result["workflow_status"] != "pending_ai_qc":
                break
