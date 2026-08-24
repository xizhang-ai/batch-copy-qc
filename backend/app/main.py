from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.assistant import router as assistant_router
from .api.copy_types import router as copy_types_router
from .api.errors import install_error_handlers
from .api.exports import router as exports_router
from .api.items import router as items_router
from .api.projects import router as projects_router
from .api.qc_rules import router as qc_rules_router
from .api.runs import router as runs_router
from .api.system import router as system_router
from .config import Settings, get_settings
from .lifespan import create_lifespan


def create_app(
    settings: Settings | None = None,
    *,
    model_adapter: Any = None,
    exporter: Any = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title="Batch Copy QC",
        version="0.1.0",
        lifespan=create_lifespan(resolved_settings, model_adapter, exporter),
    )
    install_error_handlers(app)
    app.include_router(assistant_router)
    app.include_router(projects_router)
    app.include_router(copy_types_router)
    app.include_router(qc_rules_router)
    app.include_router(runs_router)
    app.include_router(items_router)
    app.include_router(exports_router)
    app.include_router(system_router)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    frontend_dist = resolved_settings.frontend_dist_dir.resolve()
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    if (frontend_dist / "index.html").is_file():

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str) -> FileResponse:
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")

            requested = (frontend_dist / full_path).resolve()
            try:
                requested.relative_to(frontend_dist)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="Not Found") from exc

            if full_path and requested.is_file():
                return FileResponse(requested)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
