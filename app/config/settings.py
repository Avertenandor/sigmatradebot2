"""
Application settings.

Loads configuration from environment variables using pydantic-settings.
"""

import re

from loguru import logger
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Bot
    telegram_bot_token: str
    telegram_bot_username: str | None = None

    # Database
    database_url: str
    database_echo: bool = False

    # Admin
    admin_telegram_ids: str = ""  # Comma-separated list

    # Wallet
    wallet_private_key: str | None = None
    wallet_address: str
    usdt_contract_address: str
    rpc_url: str
    system_wallet_address: str  # System wallet for deposits
    # Payout wallet (optional, defaults to wallet_address)
    payout_wallet_address: str | None = None

    # Deposit levels (USDT amounts)
    deposit_level_1: float = Field(
        default=50.0, gt=0, description="Deposit level 1 amount"
    )
    deposit_level_2: float = Field(
        default=100.0, gt=0, description="Deposit level 2 amount"
    )
    deposit_level_3: float = Field(
        default=250.0, gt=0, description="Deposit level 3 amount"
    )
    deposit_level_4: float = Field(
        default=500.0, gt=0, description="Deposit level 4 amount"
    )
    deposit_level_5: float = Field(
        default=1000.0, gt=0, description="Deposit level 5 amount"
    )

    # Redis (for FSM storage and Dramatiq)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0

    # Security
    secret_key: str
    encryption_key: str

    # Application
    environment: str = "production"
    debug: bool = False
    log_level: str = "INFO"

    # Broadcast settings
    broadcast_rate_limit: int = 15  # messages per second
    broadcast_cooldown: int = 900  # 15 minutes in seconds

    # ROI settings
    roi_daily_percent: float = Field(
        default=0.02, gt=0, le=1.0,
        description="Daily ROI percentage (0-100%)"
    )
    roi_cap_multiplier: float = Field(
        default=5.0, gt=0, le=10.0, description="ROI cap multiplier"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode='after')
    def validate_production(self) -> 'Settings':
        """Validate production-specific requirements."""
        if self.environment == 'production':
            # DEBUG must be False in production
            if self.debug:
                raise ValueError(
                    'DEBUG must be False in production environment. '
                    'Set DEBUG=false in your .env file.'
                )

            # Ensure secure keys are set
            if not self.secret_key or len(self.secret_key) < 32:
                raise ValueError(
                    'SECRET_KEY must be at least 32 characters in '
                    'production. Generate one with: openssl rand -hex 32'
                )

            if not self.encryption_key or len(self.encryption_key) < 32:
                raise ValueError(
                    'ENCRYPTION_KEY must be at least 32 characters in '
                    'production. Generate one with: openssl rand -hex 32'
                )

            # Wallet private key is optional - can be set via bot interface
            # Only warn if it's a placeholder, but don't block startup
            if self.wallet_private_key and 'your_' in self.wallet_private_key.lower():
                logger.warning(
                    'WALLET_PRIVATE_KEY appears to be a placeholder. '
                    'Set a real key via /wallet_menu in the bot interface.'
                )

            # Ensure database URL is not using default passwords
            # Check for common insecure patterns like user:password@
            # or postgres:postgres@
            insecure_patterns = [
                ':password@',
                ':changeme@',
                'postgres:postgres@',
                'admin:admin@',
                'root:root@',
            ]
            if any(pattern in self.database_url.lower()
                   for pattern in insecure_patterns):
                raise ValueError(
                    'DATABASE_URL must not use default passwords '
                    'in production'
                )

        return self

    @field_validator('telegram_bot_token')
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate Telegram bot token format."""
        pattern = r'^\d+:[A-Za-z0-9_-]{35}$'
        if not re.match(pattern, v):
            raise ValueError(
                'Invalid Telegram bot token format. '
                'Expected format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz'
            )
        return v

    @field_validator('wallet_address', 'system_wallet_address')
    @classmethod
    def validate_eth_address(cls, v: str) -> str:
        """Validate Ethereum address format."""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError(
                f'Invalid Ethereum address: {v}. '
                'Must start with 0x and be 42 characters long.'
            )
        try:
            int(v[2:], 16)
        except ValueError as exc:
            raise ValueError(f'Invalid Ethereum address format: {v}') from exc
        return v.lower()

    @field_validator('usdt_contract_address')
    @classmethod
    def validate_contract_address(cls, v: str) -> str:
        """Validate USDT contract address."""
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid contract address format')
        return v.lower()

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL."""
        if not v.startswith(('postgresql://', 'postgresql+asyncpg://')):
            raise ValueError(
                'DATABASE_URL must start with postgresql:// or postgresql+asyncpg://'
            )
        return v

    def get_admin_ids(self) -> list[int]:
        """Parse admin IDs from comma-separated string with error handling."""
        if not self.admin_telegram_ids:
            return []

        result = []
        for id_ in self.admin_telegram_ids.split(","):
            id_stripped = id_.strip()
            if not id_stripped:
                continue
            try:
                result.append(int(id_stripped))
            except ValueError:
                logger.warning(f"Invalid admin ID: {id_stripped}")
                continue
        return result


# Global settings instance
settings = Settings()
