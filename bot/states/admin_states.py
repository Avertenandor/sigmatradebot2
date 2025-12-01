"""
Admin States
FSM states for admin operations
"""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """States for admin operations"""

    # Authentication
    awaiting_master_key_input = State()  # Waiting for master key input

    # User management
    awaiting_user_to_ban = State()  # Legacy, kept for compatibility
    awaiting_user_to_block = State()  # Block user (with appeal)
    awaiting_user_to_terminate = State()  # Terminate user (no appeal)
    awaiting_user_to_unban = State()  # Unban user confirmation
    finding_user = State()  # Searching for a user
    changing_user_balance = State()  # Changing user balance
    
    # Broadcast
    awaiting_broadcast_message = State()
    awaiting_broadcast_button_choice = State()  # Waiting for choice (add button or send)
    awaiting_broadcast_button_link = State()  # Waiting for button text|url
    awaiting_user_message_target = State()
    awaiting_user_message_content = State()
    
    # Support
    awaiting_support_reply = State()  # Waiting for admin reply text
    
    # Blacklist notification texts
    awaiting_block_notification_text = State()  # Waiting for block notification text
    awaiting_terminate_notification_text = State()  # Waiting for terminate notification text
    
    # Withdrawal management
    selecting_withdrawal = State()  # Selecting withdrawal ID to manage
    viewing_withdrawal = State()    # Viewing details (Approve/Reject options)
    confirming_withdrawal_action = State()  # Confirming approve/reject