from backend.app.db.repositories import Repository


def test_assistant_messages_and_action_receipts_are_saved_in_order(repository: Repository):
    project = repository.create_project("assistant repository")
    session = repository.create_or_get_assistant_session(project["id"])

    repository.append_assistant_message(session["id"], "user", "写 20 篇通勤文案")
    repository.append_assistant_message(
        session["id"],
        "assistant",
        "我会先做预览",
        plan={"summary": "x", "blockers": [], "assumptions": [], "actions": []},
    )
    repository.save_action_receipt(session["id"], "set-name", {"project_id": project["id"]})

    messages = repository.list_assistant_messages(session["id"])
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["plan"] == {"summary": "x", "blockers": [], "assumptions": [], "actions": []}
    assert repository.get_action_receipt(session["id"], "set-name") == {"project_id": project["id"]}


def test_preview_generation_run_persists_full_target_and_phase(repository: Repository):
    project = repository.create_project("preview repository")
    run = repository.create_generation_run(
        project["id"],
        20,
        {},
        generation_mode="preview",
        preview_item_count=3,
    )

    assert run["requested_count"] == 20
    assert run["generation_mode"] == "preview"
    assert run["generation_phase"] == "preview_running"
    assert run["preview_item_count"] == 3
