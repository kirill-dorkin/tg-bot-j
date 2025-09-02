from __future__ import annotations

from typing import Any

import httpx


def create_async_client(connect: int, read: int, total: int) -> httpx.AsyncClient:
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    timeout = httpx.Timeout(connect=connect, read=read, write=read, pool=total)
    return httpx.AsyncClient(limits=limits, timeout=timeout)

