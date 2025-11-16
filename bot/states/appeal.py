"""
Appeal FSM states.

States for user appeal process.
"""

from aiogram.fsm.state import State, StatesGroup


class AppealStates(StatesGroup):
    """Appeal flow states."""

    waiting_for_appeal_text = State()
