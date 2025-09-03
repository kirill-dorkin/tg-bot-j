from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SearchFSM(StatesGroup):
    """Minimal search parameter flow."""

    role = State()
    location = State()
