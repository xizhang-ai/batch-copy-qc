def test_project_create_and_patch_ignores_read_only_fields(client):
    created = client.post(
        "/api/projects",
        json={"name": "清爽气泡水", "brand": "微沫", "category": "即饮饮料"},
    ).json()
    assert created["id"]
    assert created["brand"] == "微沫"
    assert created["category"] == "即饮饮料"
    updated = client.patch(
        f"/api/projects/{created['id']}",
        json={
            "brand": "清爽实验室",
            "created_at": "malicious",
            "project_id": "bad",
            "confirmed": True,
        },
    ).json()
    assert updated["brand"] == "清爽实验室"
    assert updated["created_at"] != "malicious"


def test_brief_parse_returns_four_sections(client):
    project = client.post("/api/projects", json={"name": "清爽气泡水"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/briefs:parse",
        data={"text": "项目名称：夏日气泡水\n品牌：清爽实验室\n禁止宣称治疗"},
    )
    assert response.status_code == 200, response.text
    sections = response.json()["sections"]
    assert set(sections) == {"project_content", "copy_requirements", "project_qc", "conflicts"}


def test_project_brief_uses_semantic_sections_and_confirmed_qc_becomes_editable_rule(client):
    project = client.post("/api/projects", json={"name": "语义拆分"}).json()
    parsed = client.post(
        f"/api/projects/{project['id']}/briefs:parse",
        data={"text": "产品：青柠气泡水\n语气：轻松自然\n禁止宣称治疗"},
    ).json()

    assert parsed["sections"]["project_content"][0]["section"] == "product"
    assert parsed["sections"]["copy_requirements"][0]["section"] == "tone"
    assert parsed["sections"]["project_qc"][0]["section"] == "claim"

    saved = client.patch(
        f"/api/projects/{project['id']}",
        json={"findings": parsed["findings"], "confirmed": False},
    )
    assert saved.status_code == 200
    assert client.get(f"/api/projects/{project['id']}/qc-rules").json() == []

    confirmed = client.patch(f"/api/projects/{project['id']}", json={"confirmed": True})
    assert confirmed.status_code == 200
    rules = client.get(f"/api/projects/{project['id']}/qc-rules").json()
    assert len(rules) == 1
    assert rules[0]["scope"] == "project"
    assert rules[0]["level"] == "hard"
    assert rules[0]["category"] == "claim"
    assert rules[0]["statement"] == "禁止宣称治疗"
    assert rules[0]["source_kind"] == "derived_project_brief"

    edited = client.patch(f"/api/qc-rules/{rules[0]['id']}", json={"statement": "不得宣称治疗效果"})
    assert edited.status_code == 200

    client.patch(
        f"/api/projects/{project['id']}",
        json={"findings": parsed["findings"], "confirmed": True},
    )
    assert len(client.get(f"/api/projects/{project['id']}/qc-rules").json()) == 1


def test_brief_requires_exactly_one_input(client):
    project = client.post("/api/projects", json={"name": "清爽气泡水"}).json()
    response = client.post(f"/api/projects/{project['id']}/briefs:parse")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BRIEF_INPUT_EXCLUSIVE"


def test_request_validation_uses_standard_error_envelope(client):
    response = client.post("/api/projects", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert response.json()["error"]["details"]["errors"]
