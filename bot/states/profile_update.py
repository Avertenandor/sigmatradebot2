"""
Profile update FSM states.

States for updating user profile information (contacts).
"""

from aiogram.fsm.state import State, StatesGroup


class ProfileUpdateStates(StatesGroup):
    """FSM states for profile updates."""

    choosing_contact_type = State()
    waiting_for_phone = State()
    waiting_for_email = State()

