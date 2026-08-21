from .test_generation_run import _configured_project, _wait_run


def test_export_api_writes_only_completed_and_is_idempotent(client):
    project, _copy_type = _configured_project(client)
    generation = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    _wait_run(client, generation["id"])
    payload = {
        "export_run_id": "export-demo",
        "generation_run_id": generation["id"],
        "sheet_title": "演示输出",
    }
    first = client.post(f"/api/projects/{project['id']}/exports", json=payload)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/projects/{project['id']}/exports", json=payload)
    assert second.status_code == 201, second.text
    assert first.json()["sheet_id"] == second.json()["sheet_id"] == "fake-export-demo"
    assert len(client.app.state.exporter.recorder.created) == 1
    assert len(client.app.state.exporter.recorder.writes["fake-export-demo"]) == 1
    listed = client.get(f"/api/projects/{project['id']}/exports").json()
    assert [run["id"] for run in listed] == ["export-demo"]


def test_default_export_uses_latest_visible_batch_and_never_all_history(client):
    project, _copy_type = _configured_project(client)
    first = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    _wait_run(client, first["id"])
    second = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    _wait_run(client, second["id"])
    client.patch(f"/api/generation-runs/{second['id']}", json={"archived": True})

    response = client.post(
        f"/api/projects/{project['id']}/exports",
        json={"export_run_id": "default-visible", "sheet_title": "当前可见批"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["generation_run_id"] == first["id"]
    assert response.json()["row_count"] == 1


def test_export_rejects_generation_run_from_another_project(client):
    project, _copy_type = _configured_project(client)
    other, _other_type = _configured_project(client)
    other_run = client.post(
        f"/api/projects/{other['id']}/generation-runs", json={}
    ).json()
    _wait_run(client, other_run["id"])

    response = client.post(
        f"/api/projects/{project['id']}/exports",
        json={"generation_run_id": other_run["id"]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RUN_NOT_FOUND"
