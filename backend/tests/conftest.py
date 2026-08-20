from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_path=tmp_path / "test.sqlite3",
        upload_dir=tmp_path / "uploads",
        model_adapter="fake",
        feishu_adapter="fake",
    )


@pytest.fixture
def fake_model():
    from backend.app.model.fake import FakeModelAdapter

    return FakeModelAdapter()


@pytest.fixture
def client(settings, fake_model) -> TestClient:
    with TestClient(create_app(settings, model_adapter=fake_model)) as test_client:
        yield test_client


@pytest.fixture
def repository(client):
    return client.app.state.repository
