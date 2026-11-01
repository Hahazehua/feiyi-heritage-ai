"""Same-origin public web API. No keys, prompts or inquiry contents in logs."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from heritagelink.vector_search import CatalogSearchError
from heritagelink.web.schemas import Brief, InquiryInput
from heritagelink.web.service import HeritageService
from heritagelink.web.store import (
    FirestoreStore,
    IdempotencyConflict,
    QuotaExceeded,
    SQLiteStore,
    digest,
)

ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger("haha.web")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


def create_app(service=None, store=None, root: Path = ROOT) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.service = service or HeritageService(root)
        app.state.store = store or (
            FirestoreStore(
                os.environ["GOOGLE_CLOUD_PROJECT"], os.getenv("FIRESTORE_DATABASE", "(default)")
            )
            if os.getenv("WEB_STORE", "sqlite") == "firestore"
            else SQLiteStore(root / ".local/web-inquiries.sqlite3")
        )
        yield

    app = FastAPI(title="HAHA Heritage Studio", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        start = time.perf_counter()
        request.state.request_id = secrets.token_hex(8)
        if request.method in {"POST", "PUT", "DELETE"}:
            origin = request.headers.get("origin")
            if (origin and urlsplit(origin).netloc != request.headers.get("host")) or (
                request.headers.get("x-requested-with") != "HAHA-Studio"
            ):
                return JSONResponse({"detail": "Request origin rejected."}, status_code=403)
            body = await request.body()
            if len(body) > 16000:
                return JSONResponse({"detail": "Request too large."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            logger.info(
                json.dumps(
                    {
                        "event": "request",
                        "request_id": request.state.request_id,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - start) * 1000),
                    }
                )
            )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {"detail": "Please check the form values and consent."}, status_code=422
        )

    @app.exception_handler(QuotaExceeded)
    async def quota_error(request, exc):
        return JSONResponse(
            {"detail": "Today's demo request limit is reached. Try tomorrow."}, status_code=429
        )

    @app.exception_handler(IdempotencyConflict)
    async def duplicate_error(request, exc):
        return JSONResponse(
            {"detail": "This save key was already used for different contents."}, status_code=409
        )

    @app.exception_handler(CatalogSearchError)
    async def search_error(request, exc):
        return JSONResponse(
            {"detail": "The source index is unavailable. Please try again later."}, status_code=503
        )

    def owner(request: Request) -> str:
        token = request.cookies.get("haha_session", "")
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise HTTPException(401, "Please refresh the page to start a browser session.")
        return digest(token)

    def storage_call(fn, *args):
        try:
            return fn(*args)
        except (QuotaExceeded, IdempotencyConflict):
            raise
        except Exception:
            raise HTTPException(503, "Saved workspace is temporarily unavailable.") from None

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/session")
    def session(request: Request):
        response = JSONResponse({"ready": True, "identity": "anonymous_browser"})
        if not re.fullmatch(r"[a-f0-9]{64}", request.cookies.get("haha_session", "")):
            response.set_cookie(
                "haha_session",
                secrets.token_hex(32),
                max_age=2592000,
                httponly=True,
                secure=bool(os.getenv("K_SERVICE")),
                samesite="strict",
            )
        return response

    @app.get("/api/catalog")
    def catalog(request: Request):
        return {"items": request.app.state.service.catalog()}

    @app.post("/api/advice")
    def advice(brief: Brief, request: Request):
        store = request.app.state.store
        storage_call(store.consume, owner(request), "advice", 10, 100)
        result = request.app.state.service.advise(brief)
        result["trace"]["request_id"] = request.state.request_id
        logger.info(json.dumps({"event": "advice", "status": result["status"], **result["trace"]}))
        return result

    @app.get("/api/inquiries")
    def inquiries(request: Request):
        return {"items": storage_call(request.app.state.store.list, owner(request))}

    @app.post("/api/inquiries")
    def save_inquiry(body: InquiryInput, request: Request):
        session_owner = owner(request)
        candidates = request.app.state.service.shortlist(body.brief)
        product = next((p for p in candidates if p["id"] == body.product_id), None)
        if not product:
            raise HTTPException(422, "Please select a current match for this brief.")
        store = request.app.state.store
        storage_call(store.consume, session_owner, "inquiry", 20, 200)
        return storage_call(
            store.save,
            session_owner,
            body.idempotency_key,
            {
                "brief": body.brief.model_dump(),
                "product": product,
                "notes": body.notes,
                "consent": True,
                "status": "saved_draft_not_sent",
                "data_label": "MVP demo data",
            },
        )

    app.mount("/assets/catalog", StaticFiles(directory=root / "assets/catalog"), name="catalog")
    dist = root / "web/dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="web-assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

    return app


app = create_app()
