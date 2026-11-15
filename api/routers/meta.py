"""App status and the profile list."""
from fastapi import APIRouter, Depends

from api.deps import Core, core

router = APIRouter(prefix="/api")


@router.get("/status")
def status(c: Core = Depends(core)):
    s = c.settings
    return {"has_key": bool(s.api_key), "model": s.model, "fast_model": s.fast_model,
            "fallback_model": s.fallback_model, "audio_seconds": s.audio_seconds,
            "limits": {"file_mb": s.limits.file_bytes // 1024**2, "pages": s.limits.pages,
                       "text_chars": s.limits.text_chars}}


@router.get("/profiles")
def profiles(c: Core = Depends(core)):
    return [{"id": r.id, "revision": r.revision, "name": r.profile.name, "role": r.profile.role,
             "company": r.profile.company, "projects": len(r.profile.projects)} for r in c.store.profiles()]
