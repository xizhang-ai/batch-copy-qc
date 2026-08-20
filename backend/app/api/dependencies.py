from collections.abc import Iterator

from fastapi import Depends, Request

from ..config import Settings
from ..db.connection import connect
from ..db.repositories import Repository
from ..qc.service import QcService


def get_repository(request: Request) -> Iterator[Repository]:
    connection = connect(request.app.state.settings.database_path, set_journal_mode=False)
    try:
        yield Repository(connection)
    finally:
        connection.close()


def get_request_qc_service(
    request: Request,
    repository: Repository = Depends(get_repository),
) -> QcService:
    template = request.app.state.qc_service
    return QcService(
        repository,
        template.model_adapter,
        auto_rewrite_limit=template.auto_rewrite_limit,
        retry_limit=template.retry_limit,
        confidence_threshold=template.confidence_threshold,
        similarity_threshold=template.similarity_threshold,
    )


def get_model_adapter(request: Request):
    return request.app.state.model_adapter


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings
