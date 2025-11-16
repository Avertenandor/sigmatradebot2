"""
Admin Management States.

FSM states for new admin operations.
"""

from aiogram.fsm.state import State, StatesGroup


class AdminManagementStates(StatesGroup):
    """States for admin management."""

    waiting_for_telegram_id = State()
    waiting_for_role = State()


class DepositSettingsStates(StatesGroup):
    """States for deposit settings."""

    waiting_for_max_level = State()


class WalletManagementStates(StatesGroup):
    """States for wallet management."""

    waiting_for_wallet_type = State()
    waiting_for_new_address = State()
    waiting_for_private_key = State()
    waiting_for_reason = State()


class BlacklistStates(StatesGroup):
    """States for blacklist management."""

    waiting_for_identifier = State()
    waiting_for_reason = State()
    waiting_for_removal_identifier = State()
