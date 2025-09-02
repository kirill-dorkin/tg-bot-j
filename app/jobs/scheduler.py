from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class Scheduler:
    def __init__(self):
        self._tasks: list[asyncio.Task] = []

    def cron_daily(self, hour: int, minute: int, coro: Callable[[], Awaitable[None]]):
        async def runner():
            while True:
                await asyncio.sleep(3600)  # placeholder; real cron parsing omitted
                await coro()

        self._tasks.append(asyncio.create_task(runner()))

    async def stop(self):
        for t in self._tasks:
            t.cancel()

