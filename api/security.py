"""Local-only API protection: loopback Host, same-app Origin, and a custom header on writes."""
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

LOOPBACK = ("127.0.0.1", "localhost", "[::1]")


def install(app, *, ports=(8000, 3000), extra_hosts=()):
    hosts = set(LOOPBACK) | set(extra_hosts)
    origins = [f"http://{host}:{port}" for host in LOOPBACK for port in ports]

    @app.middleware("http")
    async def guard(request, call_next):
        if request.url.path.startswith("/api"):
            host = request.headers.get("host", "")
            name = host.rsplit(":", 1)[0] if not host.endswith("]") else host  # keep [::1] intact
            if name not in hosts:  # blocks DNS rebinding: a hostile site resolving to 127.0.0.1
                return JSONResponse({"message": "This address is not allowed."}, status_code=403)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                if request.headers.get("x-crackmate") != "1" or (origin and origin not in origins):
                    return JSONResponse({"message": "Request blocked for your protection."}, status_code=403)
        return await call_next(request)

    # Added last so it is outermost: preflights are answered before the guard runs.
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"],
                       allow_headers=["Content-Type", "X-CrackMate"])
