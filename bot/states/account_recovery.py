"""
Account Recovery FSM states.

R16-3: States for account recovery flow when user loses Telegram access.
"""

from aiogram.fsm.state import State, StatesGroup


class AccountRecoveryStates(StatesGroup):
    """States for account recovery flow."""

    waiting_for_wallet = State()  # Waiting for wallet address
    waiting_for_signature = State()  # Waiting for signature proof
    waiting_for_additional_info = State()  # Optional: email/phone verification

