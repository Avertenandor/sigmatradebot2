"""
Notification settings FSM states.

States for managing user notification preferences.
"""

from aiogram.fsm.state import State, StatesGroup


class NotificationSettingsStates(StatesGroup):
    """FSM states for notification settings."""

    waiting_for_setting_change = State()

