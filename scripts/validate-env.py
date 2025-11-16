#!/usr/bin/env python3
"""
Environment Variables Validation Script

Validates that all required environment variables are set and
    have valid values.
"""

import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import Settings


def validate_telegram_token(token: str) -> tuple[bool, str]:
    """Validate Telegram bot token format."""
    pattern = r"^\d+:[A-Za-z0-9_-]{35}$"
    if not re.match(pattern, token):
        return (
            False,
            "Invalid format. Expected: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        )
    return True, "OK"


def validate_wallet_address(address: str) -> tuple[bool, str]:
    """Validate Ethereum wallet address."""
    if not address or not address.startswith("0x") or len(address) != 42:
        return False, "Must start with 0x and be 42 characters"
    try:
        # Validate hex format
        int(address[2:], 16)
    except ValueError:
        return False, "Invalid hexadecimal format"
    return True, "OK"


def validate_database_url(url: str) -> tuple[bool, str]:
    """Validate database URL."""
    if not url.startswith("postgresql+asyncpg://"):
        return False, "Must use postgresql+asyncpg:// driver"
    if "changeme" in url.lower():
        return False, "Password cannot be 'changeme'"
    if "your_" in url.lower() or "placeholder" in url.lower():
        return False, "Contains placeholder values"
    return True, "OK"


def validate_env() -> tuple[bool, list[str]]:  # noqa: C901
    """
    Validate environment variables.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    try:
        settings = Settings()
    except Exception as e:
        return False, [f"Failed to load settings: {str(e)}"]

    # Required string variables
    required_strings = [
        ("telegram_bot_token", "TELEGRAM_BOT_TOKEN"),
        ("database_url", "DATABASE_URL"),
        ("wallet_private_key", "WALLET_PRIVATE_KEY"),
        ("wallet_address", "WALLET_ADDRESS"),
        ("usdt_contract_address", "USDT_CONTRACT_ADDRESS"),
        ("rpc_url", "RPC_URL"),
        ("system_wallet_address", "SYSTEM_WALLET_ADDRESS"),
        ("secret_key", "SECRET_KEY"),
        ("encryption_key", "ENCRYPTION_KEY"),
    ]

    for attr_name, env_name in required_strings:
        value = getattr(settings, attr_name, None)
        if not value or value.strip() == "":
            errors.append(f"{env_name} is not set or empty")
        elif "your_" in value.lower() or "placeholder" in value.lower():
            errors.append(f"{env_name} contains placeholder value")

    # Use detailed validation functions
    if settings.telegram_bot_token:
        is_valid, msg = validate_telegram_token(settings.telegram_bot_token)
        if not is_valid:
            errors.append(f"TELEGRAM_BOT_TOKEN: {msg}")

    if settings.wallet_address:
        is_valid, msg = validate_wallet_address(settings.wallet_address)
        if not is_valid:
            errors.append(f"WALLET_ADDRESS: {msg}")

    if settings.system_wallet_address:
        is_valid, msg = validate_wallet_address(settings.system_wallet_address)
        if not is_valid:
            errors.append(f"SYSTEM_WALLET_ADDRESS: {msg}")

    if settings.usdt_contract_address:
        is_valid, msg = validate_wallet_address(settings.usdt_contract_address)
        if not is_valid:
            errors.append(f"USDT_CONTRACT_ADDRESS: {msg}")

    if settings.database_url:
        is_valid, msg = validate_database_url(settings.database_url)
        if not is_valid:
            errors.append(f"DATABASE_URL: {msg}")

    # Validate RPC URL
    if settings.rpc_url and not (
        settings.rpc_url.startswith("http://")
        or settings.rpc_url.startswith("https://")
    ):
        errors.append("RPC_URL should be a valid HTTP/HTTPS URL")

    # Validate admin IDs (warning only, not blocking)
    admin_ids = settings.get_admin_ids()
    if not admin_ids:
        print(
            "⚠️  WARNING: ADMIN_TELEGRAM_IDS is not set or empty. Admin"
                "features may not work."
        )

    # Validate Redis settings
    if not settings.redis_host:
        errors.append("REDIS_HOST is not set")

    if settings.redis_port <= 0 or settings.redis_port > 65535:
        errors.append("REDIS_PORT should be between 1 and 65535")

    # Validate secret keys length
    if settings.secret_key and len(settings.secret_key) < 32:
        errors.append("SECRET_KEY should be at least 32 characters")

    if settings.encryption_key and len(settings.encryption_key) < 32:
        errors.append("ENCRYPTION_KEY should be at least 32 characters")

    return len(errors) == 0, errors


def main():
    """Main function."""

    print("🔍 Validating environment variables...")
    print("")

    is_valid, errors = validate_env()

    if is_valid:
        print("✅ All environment variables are valid!")
        print("")
        print("Environment is ready for deployment.")
        return 0
    else:
        print("❌ Environment validation failed!")
        print("")
        print("Errors found:")
        for error in errors:
            print(f"  - {error}")
        print("")
        print("Please fix the errors and try again.")
        print("You can use scripts/setup-env.sh to help configure .env file.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
