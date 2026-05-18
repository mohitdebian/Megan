"""
API Schemas — Pydantic models for WebSocket and REST API.
"""

from pydantic import BaseModel
from typing import Any


class WSMessage(BaseModel):
    """Incoming WebSocket message."""
    type: str
    data: dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    services: dict[str, str] = {}


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10


class IndexRequest(BaseModel):
    path: str
    max_depth: int = 4
