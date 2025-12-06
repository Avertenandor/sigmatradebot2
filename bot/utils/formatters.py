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
    result = str(text)
    # Order matters: escape backslash first to avoid double-escaping
    for char in ['_', '*', '`', '[']:
        result = result.replace(char, f'\\{char}')
    return result


def escape_markdown_v2(text: str | None) -> str:
    """
    Escape special characters for MarkdownV2.
    
    MarkdownV2 requires escaping more characters:
    _ * [ ] ( ) ~ ` > # + - = | { } . !
    
    Args:
        text: Input text
        
    Returns:
        Escaped text safe for MarkdownV2
    """
    if not text:
        return ""
    result = str(text)
    # Characters that need escaping in MarkdownV2
    special_chars = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', 
                     '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    return result


def safe_username(username: str | None, default: str = "пользователь") -> str:
    """
    Return escaped username safe for Markdown.
    
    Args:
        username: Telegram username (may contain underscores)
        default: Default value if username is None
        
    Returns:
        Escaped username or default value
    """
    if not username:
        return default
    return escape_md(username)


def safe_referral_code(code: str | None) -> str:
    """
    Return escaped referral code safe for Markdown.
    
    Referral codes are base64url-safe and may contain _ and -
    
    Args:
        code: Referral code
        
    Returns:
        Escaped code or empty string
    """
    if not code:
        return ""
    return escape_md(code)


def safe_wallet_address(address: str | None) -> str:
    """
    Return escaped wallet address safe for Markdown.
    
    Args:
        address: Wallet address
        
    Returns:
        Escaped address or empty string
    """
    if not address:
        return ""
    return escape_md(address)


def safe_user_text(text: str | None, max_length: int = 500) -> str:
    """
    Escape user-provided text for safe Markdown display.
    
    Truncates if too long and escapes all special characters.
    
    Args:
        text: User input text
        max_length: Maximum length before truncation
        
    Returns:
        Escaped and possibly truncated text
    """
    if not text:
        return ""
    result = str(text)
    if len(result) > max_length:
        result = result[:max_length] + "..."
    return escape_md(result)