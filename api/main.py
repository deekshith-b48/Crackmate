"""CrackMate API. Run: .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000"""
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from api import security
from api.deps import build_core, wire
from api.errors import describe
from api.routers import ask, career, learn, meta, practice, profiles, track, usage

STATIC = Path(__file__).resolve().parent.parent / "web" / "out"


def create_app(core=None, *, extra_hosts=(), serve_web=True):
    @asynccontextmanager
    async def lifespan(app):
        app.state.core = core or build_core()
        yield

    app = FastAPI(title="CrackMate", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    if core is not None:
        app.state.core = wire(core)  # tests that skip the lifespan still work
    security.install(app, ports=(int(os.environ.get("CRACKMATE_PORT", 8000)), 3000), extra_hosts=extra_hosts)  # set CRACKMATE_PORT if 8000 is taken

    @app.exception_handler(Exception)
    async def friendly(_: Request, exc: Exception):
        status, message = describe(exc)
        return JSONResponse({"message": message}, status_code=status)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        return JSONResponse({"message": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_: Request, exc: RequestValidationError):
        return JSONResponse({"message": "Some fields are missing or invalid. Check your entries and try again."}, status_code=422)

    app.include_router(meta.router)
    app.include_router(profiles.router)
    app.include_router(learn.router)
    app.include_router(practice.router)
    app.include_router(track.router)
    app.include_router(career.router)
    app.include_router(usage.router)
    app.include_router(ask.router)
    if serve_web and STATIC.is_dir():  # must come last so /api routes win
        app.mount("/", StaticFiles(directory=STATIC, html=True), name="web")
    return app


app = create_app()
