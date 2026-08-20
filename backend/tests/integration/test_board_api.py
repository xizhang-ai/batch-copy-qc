from .test_generation_run import _configured_project, _wait_run


def test_board_always_has_five_columns_and_consistent_stats(client):
    project, _copy_type = _configured_project(client, quantity=2)
    run = client.post(f"/api/projects/{project['id']}/generation-runs", json={}).json()
    _wait_run(client, run["id"])
    board = client.get(f"/api/projects/{project['id']}/board").json()
    assert set(board["columns"]) == {
        "pending_ai_qc",
        "ai_qc_running",
        "ai_rewrite_running",
        "human_review",
        "completed",
    }
    assert board["stats"]["total"] == sum(column["count"] for column in board["columns"].values())
    assert board["stats"]["ai_processing"] == (
        board["columns"]["ai_qc_running"]["count"] + board["columns"]["ai_rewrite_running"]["count"]
    )
