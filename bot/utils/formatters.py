"""
Formatters
Utility functions for formatting data
"""

from decimal import Decimal


def format_usdt(amount: Decimal | float | int) -> str:
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


def format_tx_hash_with_link(tx_hash: str | None) -> str:
    """
    Format TX hash with BSCScan link for Telegram.
    
    Args:
        tx_hash: Transaction hash
        
    Returns:
        Formatted string with shortened hash and link
        Example: `0x1234...5678` [🔗](https://bscscan.com/tx/0x...)
    """
    if not tx_hash:
        return "—"
    
    if len(tx_hash) > 20:
        short = f"{tx_hash[:10]}...{tx_hash[-8:]}"
        return f"`{short}` [🔗](https://bscscan.com/tx/{tx_hash})"
    
    return f"`{tx_hash}`"


def escape_md(text: str | None) -> str:
    """
    Escape special characters for Markdown V1.
    
    Escapes: _ * ` [
    
    Args:
        text: Input text
        
    Returns:
        Escaped text safe for Markdown
    """
    if not text:
        return ""
    return str(text).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")