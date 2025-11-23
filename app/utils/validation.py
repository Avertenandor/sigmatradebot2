"""Enhanced validation utilities."""

import re
from decimal import Decimal

from web3 import Web3


def validate_bsc_address(address: str, checksum: bool = True) -> bool:
    """
    Validate BSC wallet address.

    Args:
        address: Wallet address
        checksum: Whether to validate checksum

    Returns:
        True if valid
    """
    if not address or not isinstance(address, str):
        return False

    # Basic format check
    if not address.startswith("0x") or len(address) != 42:
        return False

    # Hex validation
    try:
        int(address[2:], 16)
    except ValueError:
        return False

    # Checksum validation (if enabled)
    if checksum:
        try:
            return Web3.is_checksum_address(address)
        except Exception:
            return False

    return True


def normalize_bsc_address(address: str) -> str:
    """
    Normalize BSC address to checksum format.

    Args:
        address: Wallet address

    Returns:
        Checksummed address

    Raises:
        ValueError: If invalid address
    """
    if not validate_bsc_address(address, checksum=False):
        raise ValueError(f"Invalid BSC address: {address}")

    return Web3.to_checksum_address(address)


def validate_usdt_amount(
    amount: Decimal,
    min_amount: Decimal = Decimal("0.01"),
    max_amount: Decimal = Decimal("1000000"),
) -> bool:
    """
    Validate USDT amount.

    Args:
        amount: Amount to validate
        min_amount: Minimum amount
        max_amount: Maximum amount

    Returns:
        True if valid
    """
    if not isinstance(amount, Decimal):
        return False

    if amount <= 0:
        return False

    if amount < min_amount or amount > max_amount:
        return False

    return True


def validate_transaction_hash(tx_hash: str) -> bool:
    """
    Validate BSC transaction hash.

    Args:
        tx_hash: Transaction hash

    Returns:
        True if valid
    """
    if not tx_hash or not isinstance(tx_hash, str):
        return False

    # Must start with 0x and be 66 chars (0x + 64 hex chars)
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        return False

    # Validate hex
    try:
        int(tx_hash[2:], 16)
        return True
    except ValueError:
        return False


def validate_telegram_username(username: str) -> bool:
    """
    Validate Telegram username format.

    Args:
        username: Username (with or without @)

    Returns:
        True if valid
    """
    if not username:
        return False

    # Remove @ if present
    if username.startswith("@"):
        username = username[1:]

    # Must be 5-32 chars, alphanumeric + underscore
    if len(username) < 5 or len(username) > 32:
        return False

    pattern = r"^[a-zA-Z0-9_]+$"
    return bool(re.match(pattern, username))


def sanitize_input(text: str, max_length: int = 500) -> str:
    """
    Sanitize user input.

    Args:
        text: User input
        max_length: Maximum length

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Trim whitespace
    text = text.strip()

    # Limit length
    if len(text) > max_length:
        text = text[:max_length]

    # Remove null bytes
    text = text.replace("\x00", "")

    return text
