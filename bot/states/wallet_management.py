"""
Wallet Management states.
"""

from aiogram.fsm.state import State, StatesGroup


class WalletManagementStates(StatesGroup):
    """FSM states for wallet management."""
    
    menu = State()
    selecting_currency_to_send = State()
    input_address_to_send = State()
    input_amount_to_send = State()
    confirm_transaction = State()

