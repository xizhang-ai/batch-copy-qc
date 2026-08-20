from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def _settings(tmp_path: Path, dist: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_path=tmp_path / "static.sqlite3",
        upload_dir=tmp_path / "uploads",
        frontend_dist_dir=dist,
        model_adapter="fake",
        feishu_adapter="fake",
    )


def test_serves_built_frontend_and_spa_fallback(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<main>Batch Copy QC</main>", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")

    with TestClient(create_app(_settings(tmp_path, dist))) as client:
        assert "Batch Copy QC" in client.get("/").text
        assert "Batch Copy QC" in client.get("/projects/demo/board").text
        assert client.get("/assets/app.js").text == "console.log('ok')"
        assert client.get("/favicon.svg").text == "<svg/>"


def test_unknown_api_remains_json_404(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<main>frontend</main>", encoding="utf-8")

    with TestClient(create_app(_settings(tmp_path, dist))) as client:
        response = client.get("/api/not-a-route")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "error": {"code": "API_NOT_FOUND", "message": "API route not found", "details": {}}
    }
