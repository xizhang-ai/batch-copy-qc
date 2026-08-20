import json


def test_new_project_has_no_default_types(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    assert client.get(f"/api/projects/{project['id']}/copy-types").json() == []


def test_reference_limit_and_derived_constraints(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={
            "name": "通勤随手记",
            "quantity": 3,
            "must_include": ["通勤"],
            "must_avoid": ["治愈"],
        },
    ).json()
    rules = client.get(f"/api/projects/{project['id']}/qc-rules").json()
    assert {rule["source_kind"] for rule in rules} == {"derived_type_constraint"}
    payload = {"raw_text": "标题\n正文", "title": "标题", "body": "正文", "topics": ["#气泡水"]}
    for _ in range(5):
        assert (
            client.post(f"/api/copy-types/{copy_type['id']}/references", json=payload).status_code
            == 201
        )
    response = client.post(f"/api/copy-types/{copy_type['id']}/references", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REFERENCE_LIMIT_EXCEEDED"


def test_incomplete_reference_is_rejected(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types", json={"name": "类型", "quantity": 1}
    ).json()
    response = client.post(
        f"/api/copy-types/{copy_type['id']}/references",
        json={"raw_text": "x", "title": "", "body": "", "topics": []},
    )
    assert response.status_code == 400


def test_copy_type_brief_maps_tone_and_keeps_project_facts_as_suggestions(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "通勤", "quantity": 1},
    ).json()
    response = client.post(
        f"/api/copy-types/{copy_type['id']}/briefs:parse",
        data={
            "text": (
                "语气：轻松自然\n标题方向：通勤反差\n正文结构：场景到体验\n"
                "一定要有：通勤\n一定不要有：治愈\n品牌：清爽实验室"
            )
        },
    )

    assert response.status_code == 200, response.text
    parsed = response.json()
    assert parsed["requirements"]["tone"] == "轻松自然"
    assert parsed["requirements"]["title_direction"] == "通勤反差"
    assert parsed["must_include"] == ["通勤"]
    assert parsed["must_avoid"] == ["治愈"]
    assert parsed["project_change_suggestions"][0]["section"] == "brand"
    unchanged = client.get(f"/api/projects/{project['id']}").json()
    assert unchanged["brand"] == ""


def test_type_brief_parse_returns_editable_type_patch(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types", json={"name": "类型", "quantity": 1}
    ).json()

    response = client.post(
        f"/api/copy-types/{copy_type['id']}/briefs:parse",
        data={"text": "正文结构：通勤场景\n语气：自然克制"},
    )

    assert response.status_code == 200
    parsed = response.json()
    assert parsed["sources"] == ["brief"]
    assert parsed["parsed_finding_count"] == 2
    assert "通勤场景" in parsed["requirements"]["body_structure"]
    assert parsed["requirements"]["tone"] == "自然克制"
    assert parsed["project_change_suggestions"] == []


def test_type_brief_review_persists_decisions_without_entering_requirements(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types", json={"name": "类型", "quantity": 1}
    ).json()
    parsed = client.post(
        f"/api/copy-types/{copy_type['id']}/briefs:parse",
        data={"text": "品牌：清爽实验室\n需人工判断：口吻是否过度"},
    ).json()

    review = parsed["brief_review"]
    assert review["project_change_suggestions"][0]["section"] == "brand"
    assert review["project_change_suggestions"][0]["decision"] == "pending"
    assert review["conflicts"][0]["source_quote"] == "需人工判断：口吻是否过度"
    persisted = client.get(f"/api/copy-types/{copy_type['id']}").json()
    assert persisted["brief_review"] == review
    assert "清爽实验室" not in persisted["requirements"].values()

    review["project_change_suggestions"][0]["decision"] = "confirmed"
    review["conflicts"][0]["decision"] = "ignored"
    updated = client.patch(f"/api/copy-types/{copy_type['id']}", json={"brief_review": review})
    assert updated.status_code == 200, updated.text
    assert updated.json()["brief_review"] == review
    listed = client.get(f"/api/projects/{project['id']}/copy-types").json()
    assert listed[0]["brief_review"] == review


def test_confirmed_type_brief_qc_proposal_materializes_once(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types", json={"name": "类型", "quantity": 1}
    ).json()
    parsed = client.post(
        f"/api/copy-types/{copy_type['id']}/briefs:parse",
        data={"text": "禁止宣称治疗"},
    ).json()
    review = parsed["brief_review"]
    assert review["conflicts"][0]["section"] == "claim"
    assert client.get(f"/api/projects/{project['id']}/qc-rules").json() == []

    review["conflicts"][0]["decision"] = "confirmed"
    for _ in range(2):
        response = client.patch(f"/api/copy-types/{copy_type['id']}", json={"brief_review": review})
        assert response.status_code == 200
    rules = client.get(f"/api/projects/{project['id']}/qc-rules").json()
    assert len(rules) == 1
    assert rules[0]["scope"] == "type"
    assert rules[0]["copy_type_id"] == copy_type["id"]
    assert rules[0]["level"] == "hard"
    assert rules[0]["source_kind"] == "derived_type_brief"


def test_file_classification_uses_model_parse_and_persists_suggestion(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/type-files:classify",
        files={"files": ("通勤要求.txt", "场景：地铁通勤\n语气：轻松自然", "text/plain")},
    )

    assert response.status_code == 200, response.text
    suggestion = response.json()[0]
    assert suggestion["suggested_type"] == "地铁通勤"
    assert "场景：地铁通勤" in suggestion["evidence"]
    assert suggestion["confidence"] == "high"
    source = client.app.state.repository.get_brief_source(suggestion["id"])
    stored = json.loads(source["classification_json"])
    assert stored["suggested_type"] == "地铁通勤"
    copy_type = client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "通勤型", "quantity": 1},
    ).json()
    assigned = client.patch(
        f"/api/brief-sources/{suggestion['id']}",
        json={"copy_type_id": copy_type["id"], "confirmed": True},
    )
    assert assigned.status_code == 200
    persisted = json.loads(assigned.json()["classification_json"])
    assert persisted["suggested_type"] == "地铁通勤"
    assert persisted["assigned_type_id"] == copy_type["id"]
    listed = client.get(f"/api/projects/{project['id']}/type-files")
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": suggestion["id"],
            "filename": "通勤要求.txt",
            "suggested_type": "地铁通勤",
            "evidence": "场景：地铁通勤",
            "confidence": "high",
            "assigned_type_id": copy_type["id"],
        }
    ]

    unassigned = client.patch(
        f"/api/brief-sources/{suggestion['id']}",
        json={"copy_type_id": None, "confirmed": True},
    )
    assert unassigned.status_code == 200
    assert (
        client.get(f"/api/projects/{project['id']}/type-files").json()[0]["assigned_type_id"]
        is None
    )


def test_copy_type_update_keeps_project_total_at_one_hundred(client):
    project = client.post("/api/projects", json={"name": "demo"}).json()
    first = client.post(
        f"/api/projects/{project['id']}/copy-types", json={"name": "A", "quantity": 60}
    ).json()
    client.post(f"/api/projects/{project['id']}/copy-types", json={"name": "B", "quantity": 40})

    response = client.patch(f"/api/copy-types/{first['id']}", json={"quantity": 61})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "COPY_TYPE_TOTAL_EXCEEDED"


def test_type_scoped_rule_rejects_copy_type_from_another_project(client):
    first = client.post("/api/projects", json={"name": "first"}).json()
    second = client.post("/api/projects", json={"name": "second"}).json()
    foreign_type = client.post(
        f"/api/projects/{second['id']}/copy-types",
        json={"name": "外部类型", "quantity": 1},
    ).json()
    response = client.post(
        f"/api/projects/{first['id']}/qc-rules",
        json={
            "scope": "type",
            "copy_type_id": foreign_type["id"],
            "level": "soft",
            "category": "tone",
            "statement": "轻松",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COPY_TYPE_PROJECT_MISMATCH"
