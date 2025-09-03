"""Unified text input flow triggered by callback buttons.

This module implements a small state machine on top of
``python-telegram-bot`` 20.7. Pressing an inline button with callback data
like ``input:profile:name`` switches the user into a special "awaiting
input" mode. The next text message from the user is consumed as the value
for the requested field. The state is stored in ``context.user_data``.

Repeated presses of the same button are idempotent - the state and the
prompt are simply overwritten. Any non-text update while waiting for input
results in a gentle reminder to send text.
"""

from __future__ import annotations

from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Text prompts for different input states
PROMPTS: dict[str, str] = {
    "profile:name": "Введите имя",
    "profile:industry": "Укажите профессиональную сферу",
}


async def _on_input_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle presses on buttons with ``callback_data`` starting with ``input:``."""
    query = update.callback_query
    if not query or not query.data:
        return

    # Example: ``input:profile:name`` -> ``profile:name``
    _, state = query.data.split(":", 1)
    context.user_data["state"] = state

    prompt = PROMPTS.get(state, "Введите значение")
    await query.message.edit_text(prompt)
    await query.answer()


async def _on_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset state on navigation actions like Back/Menu."""
    context.user_data.pop("state", None)
    await update.callback_query.answer()


async def _on_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Consume the first text message after a button press."""
    state = context.user_data.get("state")
    if not state:
        # No special state - let other handlers process this message
        return

    text = (update.message.text or "").strip()
    profile: dict[str, Any] = context.user_data.setdefault("profile", {})

    if state == "profile:name":
        if not text:
            await update.message.reply_text("Имя не может быть пустым. Пришлите текст ещё раз.")
            return
        profile["name"] = text
        context.user_data["state"] = "profile:industry"
        await update.message.reply_text(f"Принял: {text}. Дальше укажите сферу.")
        return

    if state == "profile:industry":
        if not text:
            await update.message.reply_text("Сфера не может быть пустой. Пришлите текст ещё раз.")
            return
        profile["industry"] = text
        context.user_data.pop("state", None)
        await update.message.reply_text(f"Сохранил: {text}.")
        return

    # Unknown state - reset to avoid getting stuck
    context.user_data.pop("state", None)
    await update.message.reply_text("Состояние сброшено, начните заново.")


async def _on_non_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remind users to send text when in input mode and a non-text message arrives."""
    if context.user_data.get("state"):
        await update.effective_message.reply_text("Пожалуйста, пришлите текст.")


def register_input_handlers(app: Application) -> None:
    """Register callback and message handlers on the given application."""

    # Handle input triggers and navigation resets
    app.add_handler(CallbackQueryHandler(_on_input_button, pattern=r"^input:"))
    app.add_handler(CallbackQueryHandler(_on_nav, pattern=r"^nav:(back|menu)$"))

    # Place free text handler at the end of the chain so it doesn't conflict
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_free_text), group=1)
    app.add_handler(MessageHandler(~filters.TEXT, _on_non_text), group=1)

