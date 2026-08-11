"""Routes package exporting api and web Blueprints."""

from .api import api
from .web import web

__all__ = ["api", "web"]
