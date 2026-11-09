"""Entry point of the hosted demo (a Vercel Python function, see vercel.json).

Selects the hosted profile before any settings are read: Gemini embeddings
over the vectors shipped in marjaa/hosted/, BM25 + RRF, Gemini for answers.
The routes live under /api because Vercel passes the full request path on.

Run it locally with: make serve-hosted
"""

from __future__ import annotations

import os

os.environ.setdefault("MARJAA_PROFILE", "hosted")

from marjaa.api.app import create_app

# Load lazily: a missing GEMINI_API_KEY should fail one request with a clear
# error, not crash the function at start-up.
app = create_app(with_ui=False, preload=False, api_only=True)
