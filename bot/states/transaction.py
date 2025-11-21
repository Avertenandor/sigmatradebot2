"""
Transaction history FSM states.

States for filtering and pagination of transaction history.
"""

from aiogram.fsm.state import State, StatesGroup


class TransactionHistoryStates(StatesGroup):
    """FSM states for transaction history navigation."""

    # No active state needed - we use FSM data to store filter and page
    # This allows users to navigate without being in a specific state
    pass

