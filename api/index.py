# api/index.py
# Vercel Python serverless entry point.
# Vercel looks for a callable named `app` (ASGI/WSGI) in this file.
# We simply re-export the FastAPI `app` object from the backend package.

import sys
import os

# Make the backend package importable from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app  # noqa: F401  – re-exported for Vercel
