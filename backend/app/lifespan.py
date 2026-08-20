from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from .config import Settings
from .db.connection import connect
from .db.migrations import migrate
from .db.repositories import Repository
from .generation.worker import GenerationWorker
from .qc.service import QcService


def create_lifespan(settings: Settings, model_adapter: Any = None, exporter: Any = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        connection = connect(settings.database_path)
        migrate(connection)
        if model_adapter is None:
            from .model.factory import build_model_adapter

            resolved_model_adapter = build_model_adapter(settings)
        else:
            resolved_model_adapter = model_adapter
        app.state.settings = settings
        app.state.connection = connection
        repository = Repository(connection)
        app.state.repository = repository
        app.state.model_adapter = resolved_model_adapter
        if exporter is None:
            from .export.factory import build_exporter

            resolved_exporter = build_exporter(settings)
        else:
            resolved_exporter = exporter
        app.state.exporter = resolved_exporter
        qc_service = QcService(
            repository,
            resolved_model_adapter,
            auto_rewrite_limit=settings.auto_rewrite_limit,
            retry_limit=settings.api_retry_limit,
            confidence_threshold=settings.qc_confidence_threshold,
            similarity_threshold=settings.similarity_threshold,
        )
        worker = GenerationWorker(
            repository,
            resolved_model_adapter,
            qc_service,
            concurrency=settings.model_concurrency,
        )
        app.state.qc_service = qc_service
        app.state.generation_worker = worker
        await worker.start()
        try:
            yield
        finally:
            await worker.stop()
            connection.close()

    return lifespan
