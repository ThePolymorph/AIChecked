"""Vercel serverless entry — re-exports the FastAPI app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app  # noqa: F401
