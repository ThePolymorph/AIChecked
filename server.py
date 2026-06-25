"""AIChecked.com — FastAPI server (local + Vercel)."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from report import CombinedReport, run_combined_scan

ROOT = Path(__file__).parent
PUBLIC_DIR = ROOT / "public"
ON_VERCEL = bool(os.environ.get("VERCEL"))
MODEL_PAIR = None
MODEL_LOCK = threading.Lock()
MODEL_LOADING = False
MODEL_ERROR: Optional[str] = None

ObserverName = os.environ.get("OBSERVER_MODEL", "gpt2")
PerformerName = os.environ.get("PERFORMER_MODEL", "gpt2-medium")
EAGER_LOAD = os.environ.get("LOAD_MODELS", "0") == "1"
QUICK_ONLY = os.environ.get("QUICK_ONLY", "1" if ON_VERCEL else "1") == "1"


def _load_models() -> None:
    global MODEL_PAIR, MODEL_LOADING, MODEL_ERROR
    if MODEL_PAIR is not None:
        return
    with MODEL_LOCK:
        if MODEL_PAIR is not None:
            return
        MODEL_LOADING = True
        MODEL_ERROR = None
        try:
            from models import ModelPair

            MODEL_PAIR = ModelPair(
                observer_name=ObserverName,
                performer_name=PerformerName,
            )
        except Exception as exc:
            MODEL_ERROR = str(exc)
            raise
        finally:
            MODEL_LOADING = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    if EAGER_LOAD and not QUICK_ONLY:
        try:
            _load_models()
        except Exception:
            pass
    yield


app = FastAPI(
    title="AIChecked",
    description="AI text detection — heuristics + optional Binoculars scoring",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aichecked.com",
        "https://www.aichecked.com",
    ],
    allow_origin_regex=r"https://(.*\.vercel\.app|localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)
    mode: Literal["quick", "deep", "full"] = "quick"


class ScanResponse(BaseModel):
    ok: bool = True
    report: dict


def health_payload() -> dict:
    return {
        "status": "ok",
        "quick_only": QUICK_ONLY,
        "deep_scan_available": not QUICK_ONLY,
        "models_loaded": MODEL_PAIR is not None,
        "models_loading": MODEL_LOADING,
        "models_error": MODEL_ERROR,
        "observer": ObserverName if not QUICK_ONLY else None,
        "performer": PerformerName if not QUICK_ONLY else None,
    }


def perform_scan(req: ScanRequest) -> ScanResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Text is empty.")

    pair = None
    if req.mode in ("deep", "full"):
        if QUICK_ONLY:
            raise HTTPException(
                403,
                "Deep scan is disabled on the public site. "
                "Use Quick scan, or run the statistical scorer locally (see GitHub).",
            )
        try:
            _load_models()
        except Exception as exc:
            raise HTTPException(
                503,
                f"Statistical models unavailable: {exc}. Quick scan still works.",
            ) from exc
        if MODEL_PAIR is None:
            raise HTTPException(503, "Models failed to load.")
        pair = MODEL_PAIR

    report: CombinedReport = run_combined_scan(text, pair=pair, mode=req.mode)
    return ScanResponse(report=report.to_dict())


@app.get("/api/health")
def health():
    return health_payload()


@app.post("/api/scan", response_model=ScanResponse)
def scan(req: ScanRequest):
    return perform_scan(req)


# Local dev: serve static site from public/. On Vercel, public/ is served automatically.
if not ON_VERCEL and PUBLIC_DIR.is_dir():
    @app.get("/")
    def index():
        return FileResponse(PUBLIC_DIR / "index.html")

    app.mount("/css", StaticFiles(directory=PUBLIC_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=PUBLIC_DIR / "js"), name="js")

    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(PUBLIC_DIR / "favicon.svg")
