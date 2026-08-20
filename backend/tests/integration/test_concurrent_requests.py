from concurrent.futures import ThreadPoolExecutor


def test_parallel_http_reads_and_writes_use_isolated_sqlite_connections(client):
    project = client.post("/api/projects", json={"name": "并发项目"}).json()
    client.post(
        f"/api/projects/{project['id']}/copy-types",
        json={"name": "通勤", "quantity": 1, "brief_text": "真实体验"},
    )

    def request_once(index: int):
        operation = index % 4
        if operation == 0:
            response = client.get(f"/api/projects/{project['id']}/copy-types")
        elif operation == 1:
            response = client.get(f"/api/projects/{project['id']}/board")
        elif operation == 2:
            response = client.get(f"/api/projects/{project['id']}/type-files")
        else:
            response = client.patch(
                f"/api/projects/{project['id']}", json={"brand": f"品牌-{index}"}
            )
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(request_once, range(96)))

    assert all(status == 200 for status, _payload in results)
    assert all("error" not in payload for _status, payload in results)
    final = client.get(f"/api/projects/{project['id']}")
    assert final.status_code == 200
    assert final.json()["brand"].startswith("品牌-")
