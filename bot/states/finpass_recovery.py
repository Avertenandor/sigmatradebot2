"""
Financial Password Recovery States.

FSM states for financial password recovery flow.
"""

from aiogram.fsm.state import State, StatesGroup


class FinpassRecoveryStates(StatesGroup):
    """States for financial password recovery."""

    waiting_for_reason = State()
