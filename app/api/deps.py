"""Shared API dependencies."""

from fastapi import HTTPException, Request

from app.config.settings import settings

# Paths (relative to the /api prefix) that stay public.
_PUBLIC_SUFFIXES = ("/status",)


async def require_api_key(request: Request) -> None:
    """
    API-key auth: when settings.api_keys is non-empty, every /api route
    (except /api/status) must present a matching X-API-Key header.
    An empty API_KEYS setting disables auth for local development.
    """
    if not settings.api_keys:
        return
    if request.url.path.endswith(_PUBLIC_SUFFIXES):
        return

    provided = request.headers.get("x-api-key")
    allowed = {key.strip() for key in settings.api_keys.split(",") if key.strip()}
    if provided not in allowed:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
