from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message


router = Router()


@router.message(F.text == "/health")
async def health_cmd(m: Message, t):
    await m.answer(t("health.ok"))

