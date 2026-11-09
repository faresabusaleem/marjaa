"""Vercel entry point: the hosted Marjaa API (routes under /api)."""

from marjaa.api.hosted import app

__all__ = ["app"]
