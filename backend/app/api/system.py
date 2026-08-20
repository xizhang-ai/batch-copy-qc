from fastapi import APIRouter, Depends

from .dependencies import get_settings_dependency

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/connections")
def connections(settings=Depends(get_settings_dependency)):
    return {
        "model": {"configured": settings.model_configured, "adapter": settings.model_adapter},
        "feishu": {
            "configured": settings.feishu_configured,
            "adapter": settings.feishu_adapter,
            "spreadsheetConfigured": bool(
                settings.feishu_spreadsheet_token or settings.feishu_wiki_node_token
            ),
        },
    }
