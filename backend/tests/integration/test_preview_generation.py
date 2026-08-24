from .test_generation_run import _configured_project, _wait_run


def test_preview_creates_three_representative_slots_and_waits_for_approval(client):
    project = client.post("/api/projects", json={"name": "preview"}).json()
    client.patch(
        f"/api/projects/{project['id']}",
        json={"project_content": {"product": "气泡水"}, "confirmed": True},
    )
    client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "通勤", "quantity": 4, "brief_text": "真实体验"},
    ).json()
    client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "聚餐", "quantity": 4, "brief_text": "真实体验"},
    ).json()

    created = client.post(
        f"/api/projects/{project['id']}/generation-runs", json={"generation_mode": "preview"}
    )
    assert created.status_code == 201
    run = _wait_run(
        client,
        created.json()["id"],
        lambda value: value["generation_phase"] == "awaiting_preview_approval",
    )

    assert run["total_requested"] == 8
    assert run["preview_item_count"] == 3
    saved_type_order = client.get(f"/api/projects/{project['id']}/copy-types").json()
    preview_type_ids = [
        client.get(f"/api/items/{item_id}").json()["copy_type_id"] for item_id in run["item_ids"]
    ]
    assert preview_type_ids.count(saved_type_order[0]["id"]) == 2
    assert preview_type_ids.count(saved_type_order[1]["id"]) == 1


def test_confirm_preview_appends_remaining_slots_to_original_run_once(client):
    project, _copy_type = _configured_project(client, quantity=5)
    run_id = client.post(
        f"/api/projects/{project['id']}/generation-runs", json={"generation_mode": "preview"}
    ).json()["id"]
    ready = _wait_run(
        client, run_id, lambda value: value["generation_phase"] == "awaiting_preview_approval"
    )

    confirmed = client.post(
        f"/api/generation-runs/{run_id}/preview:confirm",
        json={"expected_preview_item_count": ready["preview_item_count"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["id"] == run_id
    assert confirmed.json()["generation_phase"] == "full_running"
    settled = _wait_run(client, run_id)
    assert len(settled["item_ids"]) == 5

    repeated = client.post(
        f"/api/generation-runs/{run_id}/preview:confirm",
        json={"expected_preview_item_count": ready["preview_item_count"]},
    )
    assert repeated.status_code == 200
    assert len(_wait_run(client, run_id)["item_ids"]) == 5
