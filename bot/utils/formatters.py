"""
Formatters
Utility functions for formatting data
"""

from decimal import Decimal
from typing import Union


def format_usdt(amount: Union[Decimal, float, int]) -> str:
    """
    Format USDT amount to 2 decimal places

    Args:
        amount: Amount to format

    Returns:
        Formatted string (e.g., "123.45")
    """
    if isinstance(amount, Decimal):
        return f"{float(amount):.2f}"
    return f"{amount:.2f}"


def format_wallet_address(address: str, show_chars: int = 6) -> str:
    """
    Format wallet address to shortened version

    Args:
        address: Full wallet address
        show_chars: Number of characters to show at start/end

    Returns:
        Shortened address (e.g., "0x1234...5678")
    """
    if len(address) <= show_chars * 2:
        return address

    return f"{address[:show_chars]}...{address[-show_chars:]}"


def format_transaction_hash(tx_hash: str, show_chars: int = 6) -> str:
    """
    Format transaction hash to shortened version

    Args:
        tx_hash: Full transaction hash
        show_chars: Number of characters to show at start/end

    Returns:
        Shortened hash (e.g., "0xabcd...ef01")
    """
    if len(tx_hash) <= show_chars * 2:
        return tx_hash

    return f"{tx_hash[:show_chars]}...{tx_hash[-show_chars:]}"
