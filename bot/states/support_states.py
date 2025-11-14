"""
Support States
FSM states for support ticket conversation
"""

from aiogram.fsm.state import State, StatesGroup


class SupportStates(StatesGroup):
    """States for support ticket creation"""

    awaiting_input = State()  # Waiting for user to add messages/attachments
