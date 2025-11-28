"""
Wallet change FSM states.
"""

from aiogram.fsm.state import State, StatesGroup


class WalletChangeStates(StatesGroup):
    """States for wallet change flow."""

    awaiting_new_wallet = State()
    awaiting_financial_password = State()

