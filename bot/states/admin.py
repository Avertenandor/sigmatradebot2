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


class AdminDepositManagementStates(StatesGroup):
    """States for deposit management."""

    searching_user_deposits = State()  # Waiting for user Telegram ID to search deposits
    viewing_user_deposits = State()  # Viewing user deposits
    managing_level = State()  # Managing specific deposit level
    confirming_level_status = State()  # Confirming enable/disable for level
    viewing_pending = State()  # Viewing pending deposits
    confirming_deposit_action = State()  # Confirming deposit action (approve/reject)
    setting_max_level = State()  # Setting max open deposit level


class AdminRoiCorridorStates(StatesGroup):
    """States for ROI corridor management."""

    selecting_level = State()  # Selecting deposit level (1-5)
    selecting_mode = State()  # Selecting mode (custom/equal)
    selecting_applies_to = State()  # Selecting when to apply (current/next)
    entering_reason = State()  # Entering optional human-readable reason
    entering_min = State()  # Entering minimum percentage (custom mode)
    entering_max = State()  # Entering maximum percentage (custom mode)
    entering_fixed = State()  # Entering fixed percentage (equal mode)
    confirming = State()  # Confirming settings
    viewing_history_level = State()  # Viewing history for specific level
    setting_period = State()  # Setting accrual period
    confirming_period = State()  # Confirming accrual period change
    selecting_level_amount = State()  # Selecting level for amount change
    setting_level_amount = State()  # Entering new amount for level
    confirming_level_amount = State()  # Confirming level amount change


class AdminSupportStates(StatesGroup):
    """States for admin support."""

    viewing_list = State()  # Viewing list of tickets
    viewing_ticket = State()  # Viewing specific ticket
    answering_ticket = State()  # Answering a ticket
    confirming_close = State()  # Confirming ticket closure
    confirming_reopen = State()  # Confirming ticket reopen


class AdminFinpassRecoveryStates(StatesGroup):
    """States for finpass recovery management."""

    viewing_list = State()  # Viewing list of requests
    viewing_request = State()  # Viewing specific request
    confirming_action = State()  # Confirming approve/reject (optional, mostly direct action)
