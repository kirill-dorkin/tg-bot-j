from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ProfileFSM(StatesGroup):
    role = State()
    skills = State()
    locations = State()
    salary_min = State()
    formats = State()
    experience = State()

