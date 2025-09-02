from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.infra.redis import KeyValueStore
from app.repositories.applied import AppliedRepo
from app.repositories.favorites import FavoritesRepo
from app.repositories.blacklist import BlacklistRepo
from app.repositories.shortkeys import ShortKeysRepo


router = Router()


@router.callback_query(F.data.startswith("act:"))
async def handle_action(cq: CallbackQuery, data: str | None, session, store: KeyValueStore, t):
    parts = cq.data.split(":")
    act = parts[1]
    key = parts[2] if len(parts) > 2 else None
    sk = ShortKeysRepo(store)
    payload = await sk.get(key) if key else None
    url = payload["args"]["url"] if payload else None

    if act == "save" and url:
        await FavoritesRepo(session).add(cq.from_user.id, url)
        await session.commit()
        await cq.answer(t("actions.saved"), show_alert=False)
    elif act == "hide":
        # Hides by company is part of pipeline; here only acknowledge
        await cq.answer(t("actions.hidden"), show_alert=False)
    elif act == "report" and url:
        # For brevity, just ack
        await cq.answer(t("actions.reported"), show_alert=False)
    elif act == "apply" and url:
        # Idempotency through Redis NX key + DB record
        idem_key = f"idemp:apply:{cq.from_user.id}|{url}"
        ok = await store.set_nx(idem_key, "1", ex=300)
        if ok:
            await AppliedRepo(session).mark(cq.from_user.id, url)
            await session.commit()
        await cq.answer(f"{t('actions.applied')} {url}")
    else:
        await cq.answer("")

