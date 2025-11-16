"""
Update contacts FSM states.

States for updating user contacts (phone/email).
"""

from aiogram.fsm.state import State, StatesGroup


class UpdateContactsStates(StatesGroup):
    """Update contacts flow states."""

    waiting_for_phone = State()
    waiting_for_email = State()
