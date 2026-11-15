"""Usage page: calls made, calls saved by caches, tokens by feature and free-tier headroom."""
from fastapi import APIRouter, Depends

from api.deps import Core, core
from core.usage import Usage

router = APIRouter(prefix="/api")


@router.get("/usage")
def usage(hours: int = 24, c: Core = Depends(core)):
    return Usage(c.store).summary(max(1, min(hours, 168)))
