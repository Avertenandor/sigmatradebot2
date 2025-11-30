"""
Admin withdrawal settings states.
"""

from aiogram.fsm.state import State, StatesGroup


class AdminWithdrawalSettingsStates(StatesGroup):
    """FSM states for admin withdrawal settings."""

    menu = State()
    waiting_for_min_amount = State()
    waiting_for_daily_limit = State()
    waiting_for_service_fee = State()

