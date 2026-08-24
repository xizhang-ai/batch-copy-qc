def test_message_returns_plan_without_mutating_project(client):
    project = client.post("/api/projects", json={"name": "助手项目"}).json()

    response = client.post(
        f"/api/projects/{project['id']}/assistant/messages",
        json={"content": "给新品写 20 篇通勤种草"},
    )

    assert response.status_code == 201
    assert response.json()["plan"]["actions"]
    assert client.get(f"/api/projects/{project['id']}").json()["status"] == "draft"


def test_apply_actions_is_idempotent(client):
    project = client.post("/api/projects", json={"name": "助手项目"}).json()
    payload = {
        "actions": [
            {
                "client_action_id": "set-project-name",
                "kind": "set_project",
                "payload": {"name": "通勤种草"},
            }
        ]
    }

    first = client.post(f"/api/projects/{project['id']}/assistant/actions:apply", json=payload)
    second = client.post(f"/api/projects/{project['id']}/assistant/actions:apply", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert client.get(f"/api/projects/{project['id']}").json()["name"] == "通勤种草"


def test_apply_actions_skips_an_incomplete_model_rule_action(client):
    project = client.post("/api/projects", json={"name": "助手项目"}).json()
    payload = {
        "actions": [
            {
                "client_action_id": "missing-rules",
                "kind": "replace_project_rules",
                "payload": {},
            },
            {
                "client_action_id": "set-project-name",
                "kind": "set_project",
                "payload": {"name": "通勤种草"},
            },
        ]
    }

    response = client.post(f"/api/projects/{project['id']}/assistant/actions:apply", json=payload)

    assert response.status_code == 200
    assert response.json()["results"][0]["skipped"] is True
    assert client.get(f"/api/projects/{project['id']}").json()["name"] == "通勤种草"


def test_apply_actions_skips_new_copy_type_without_generation_basis(client):
    project = client.post("/api/projects", json={"name": "助手项目"}).json()
    payload = {
        "actions": [
            {
                "client_action_id": "empty-copy-type",
                "kind": "upsert_copy_type",
                "payload": {"name": "家族种草", "quantity": 5},
            }
        ]
    }

    response = client.post(f"/api/projects/{project['id']}/assistant/actions:apply", json=payload)

    assert response.status_code == 200
    assert response.json()["results"][0]["skipped"] is True
    assert client.get(f"/api/projects/{project['id']}/copy-types").json() == []


def test_assistant_reuses_a_single_configured_type_for_quantity_changes(client):
    project = client.post("/api/projects", json={"name": "助手项目"}).json()
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "家族双罐", "quantity": 10, "brief_text": "母婴种草内容"},
    ).json()

    response = client.post(
        f"/api/projects/{project['id']}/assistant/messages",
        json={"content": "给新品做 5 篇家族种草"},
    )

    assert response.status_code == 201
    action = next(action for action in response.json()["plan"]["actions"] if action["kind"] == "upsert_copy_type")
    assert action["payload"] == {"id": copy_type["id"], "quantity": 5}
    applied = client.post(
        f"/api/projects/{project['id']}/assistant/actions:apply",
        json={"actions": [action]},
    )
    assert applied.status_code == 200
    assert client.get(f"/api/projects/{project['id']}/copy-types").json()[0]["quantity"] == 5


def test_assistant_session_includes_messages_and_plan(client):
    project = client.post("/api/projects", json={"name": "助手项目"}).json()
    client.post(
        f"/api/projects/{project['id']}/assistant/messages",
        json={"content": "先写 3 篇"},
    )

    response = client.get(f"/api/projects/{project['id']}/assistant/session")

    assert response.status_code == 200
    assert [row["role"] for row in response.json()["messages"]] == ["user", "assistant"]
    assert response.json()["messages"][1]["plan"]["summary"]
