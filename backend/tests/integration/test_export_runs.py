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
