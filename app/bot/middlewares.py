from __future__ import annotations

from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from app.repositories.users import UsersRepo


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, per_minute: int, store):
        super().__init__()
        self.limit = per_minute
        self.store = store

    async def __call__(self, handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]], event: Message, data: Dict[str, Any]) -> Any:  # type: ignore[override]
        user_id = event.from_user.id if getattr(event, "from_user", None) else None
        if user_id:
            key = f"rate:{user_id}"
            cur = await self.store.get(key)  # type: ignore[attr-defined]
            count = int(cur or 0)
            if count >= self.limit:
                # drop silently
                return
            if count == 0:
                await self.store.setex(key, 60, "1")  # type: ignore[attr-defined]
            else:
                await self.store.setex(key, 60, str(count + 1))  # naive TTL reset acceptable
        return await handler(event, data)


class InjectSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory):
        super().__init__()
        self.session_factory = session_factory

    async def __call__(self, handler, event, data):  # type: ignore[override]
        data["session"] = self.session_factory()
        try:
            return await handler(event, data)
        finally:
            await data["session"].close()


class I18nMiddleware(BaseMiddleware):
    def __init__(self, ru: dict[str, str], en: dict[str, str]):
        super().__init__()
        self.ru = ru
        self.en = en

    async def __call__(self, handler, event, data):  # type: ignore[override]
        # load language from users repo if possible
        session = data.get("session")
        lang = "ru"
        if session and getattr(event, "from_user", None):
            repo = UsersRepo(session)
            u_lang = await repo.get_lang(event.from_user.id)
            if u_lang:
                lang = u_lang
        t = self.ru if lang == "ru" else self.en
        data["t"] = lambda k: t.get(k, k)
        data["lang"] = lang
        return await handler(event, data)


class InjectDepsMiddleware(BaseMiddleware):
    def __init__(self, **deps):
        super().__init__()
        self.deps = deps

    async def __call__(self, handler, event, data):  # type: ignore[override]
        data.update(self.deps)
        return await handler(event, data)
