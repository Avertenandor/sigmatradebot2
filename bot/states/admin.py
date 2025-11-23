"""
Admin Management States.

FSM states for new admin operations.
"""

from aiogram.fsm.state import State, StatesGroup


class AdminManagementStates(StatesGroup):
    """States for admin management."""

    awaiting_admin_telegram_id = State()  # Waiting for Telegram ID of new admin
    awaiting_admin_role = State()  # Waiting for role selection
    awaiting_emergency_telegram_id = State()  # Waiting for Telegram ID for emergency block


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


class AdminUserMessagesStates(StatesGroup):
    """States for viewing user messages."""

    waiting_for_user_id = State()
    viewing_messages = State()  # Viewing paginated messages (stores telegram_id and page)


class AdminMasterKeyStates(StatesGroup):
    """States for master key management."""

    awaiting_confirmation = State()  # Waiting for confirmation to regenerate key