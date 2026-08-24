from __future__ import annotations

from typing import Any

from ..db.repositories import Repository
from ..domain.errors import DomainError
from ..domain.schemas import AssistantAction, AssistantPlan
from ..generation.service import GenerationService


class AssistantService:
    def __init__(self, repository: Repository, model_adapter: Any) -> None:
        self.repository = repository
        self.model_adapter = model_adapter

    async def reply(self, project_id: str, content: str) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        session = self.repository.create_or_get_assistant_session(project_id)
        self.repository.append_assistant_message(session["id"], "user", content)
        history = [
            {"role": row["role"], "content": row["content"]}
            for row in self.repository.list_assistant_messages(session["id"])
        ]
        model_project = {
            "id": project["id"],
            "name": project["name"],
            "brand": project["brand"],
            "category": project["category"],
            "confirmed": bool(project["confirmed"]),
        }
        plan: AssistantPlan = await self.model_adapter.plan_project_setup(
            model_project, history, content
        )
        message = self.repository.append_assistant_message(
            session["id"], "assistant", plan.summary, plan=plan.model_dump(mode="json")
        )
        return {"session_id": session["id"], "message": message, "plan": plan.model_dump(mode="json")}

    def session(self, project_id: str) -> dict[str, Any]:
        session = self.repository.create_or_get_assistant_session(project_id)
        return {"id": session["id"], "project_id": project_id, "messages": self.repository.list_assistant_messages(session["id"])}

    def apply_actions(self, project_id: str, actions: list[AssistantAction]) -> list[dict[str, Any]]:
        session = self.repository.create_or_get_assistant_session(project_id)
        results: list[dict[str, Any]] = []
        for action in actions:
            receipt = self.repository.get_action_receipt(session["id"], action.client_action_id)
            if receipt is not None:
                results.append(receipt)
                continue
            result = self._apply_action(project_id, action)
            self.repository.save_action_receipt(session["id"], action.client_action_id, result)
            results.append(result)
        self.repository.append_assistant_message(
            session["id"], "system", "已按你的确认更新任务配置。"
        )
        return results

    def _apply_action(self, project_id: str, action: AssistantAction) -> dict[str, Any]:
        payload = action.payload
        if action.kind == "set_project":
            allowed = {key: payload[key] for key in ("name", "brand", "category") if key in payload}
            if not allowed:
                raise DomainError("ASSISTANT_ACTION_INVALID", "Project action needs a project field", status_code=422)
            updated = self.repository.update_project(project_id, allowed)
            return {"kind": action.kind, "project_id": project_id, "project": updated}
        if action.kind == "replace_project_findings":
            findings = payload.get("findings")
            if not isinstance(findings, list):
                raise DomainError("ASSISTANT_ACTION_INVALID", "Findings action needs findings", status_code=422)
            grouped = {
                "project_content_json": {"findings": [row for row in findings if row.get("section") == "project_content"]},
                "copy_requirements_json": {"findings": [row for row in findings if row.get("section") == "copy_requirements"]},
                "qc_requirements_json": {"findings": [row for row in findings if row.get("section") == "qc_requirements"]},
                "pending_confirmation_json": [row for row in findings if row.get("section") == "needs_confirmation"],
            }
            updated = self.repository.update_project(project_id, grouped)
            return {"kind": action.kind, "project_id": project_id, "project": updated}
        if action.kind == "upsert_copy_type":
            copy_type_id = payload.get("id")
            values = {
                key: payload[key]
                for key in (
                    "name", "quantity", "brief_text", "use_reference_examples",
                    "use_description_requirements", "description_requirements", "must_include", "must_avoid",
                )
                if key in payload
            }
            if copy_type_id:
                current = self.repository.get_copy_type(str(copy_type_id))
                if current["project_id"] != project_id:
                    raise DomainError("COPY_TYPE_PROJECT_MISMATCH", "Copy type belongs to another project", status_code=409)
                update_values = {
                    (f"{key}_json" if key in {"description_requirements", "must_include", "must_avoid"} else key): value
                    for key, value in values.items()
                }
                item = self.repository.update_copy_type(str(copy_type_id), update_values)
            else:
                name = str(values.get("name") or "默认帖子类型").strip()
                item = self.repository.create_copy_type(
                    project_id,
                    name=name,
                    quantity=int(values.get("quantity", 1)),
                    **{key: value for key, value in values.items() if key not in {"name", "quantity"}},
                )
            return {"kind": action.kind, "project_id": project_id, "copy_type_id": item["id"]}
        if action.kind == "replace_project_rules":
            rules = payload.get("rules")
            if not isinstance(rules, list):
                raise DomainError("ASSISTANT_ACTION_INVALID", "Rules action needs rules", status_code=422)
            for rule in self.repository.list_rules(project_id):
                if rule["scope"] == "project":
                    self.repository.delete_rule(rule["id"])
            created = [
                self.repository.create_rule(
                    project_id,
                    scope="project",
                    level=str(rule.get("level", "hard")),
                    category=str(rule.get("category", "other")),
                    statement=str(rule["statement"]),
                    source_evidence=str(rule.get("source_evidence", "对话确认")),
                    source_kind="explicit_project_qc",
                )
                for rule in rules
            ]
            return {"kind": action.kind, "project_id": project_id, "rule_ids": [row["id"] for row in created]}
        if action.kind == "start_generation":
            mode = str(payload.get("generation_mode", "preview"))
            if mode not in {"preview", "full"}:
                raise DomainError("GENERATION_MODE_INVALID", "Generation mode is invalid", status_code=422)
            run, _items = GenerationService(self.repository).create_run(project_id, generation_mode=mode)
            return {"kind": action.kind, "project_id": project_id, "generation_run_id": run["id"]}
        raise DomainError("ASSISTANT_ACTION_INVALID", "Assistant action is unsupported", status_code=422)
