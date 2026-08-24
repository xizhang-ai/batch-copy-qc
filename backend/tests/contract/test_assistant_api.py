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
