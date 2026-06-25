"""Vercel: GET /api/health"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

from server import health_payload

app = FastAPI()


@app.get("/")
def health():
    return health_payload()
