"""Vercel: POST /api/scan"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

from server import ScanRequest, perform_scan

app = FastAPI()


@app.post("/")
def scan(req: ScanRequest):
    return perform_scan(req)
