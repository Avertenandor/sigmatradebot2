"""
Referral list FSM states.

States for navigating referral lists by level and pagination.
"""

from aiogram.fsm.state import State, StatesGroup


class ReferralListStates(StatesGroup):
    """FSM states for referral list navigation."""

    # No active state needed - we use FSM data to store level and page
    # This allows users to navigate without being in a specific state
    pass

