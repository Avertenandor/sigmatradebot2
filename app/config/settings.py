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
    
    # Blockchain RPC Providers
    rpc_url: str  # Default/Legacy RPC URL (QuickNode HTTP)
    
    # QuickNode Endpoints
    rpc_quicknode_http: str | None = None
    rpc_quicknode_wss: str | None = None
    
    # NodeReal Endpoints
    rpc_nodereal_http: str | None = None
    rpc_nodereal_wss: str | None = None

    system_wallet_address: str  # System wallet for deposits
    # Blockchain polling settings
    blockchain_poll_interval: int = Field(
        default=3, ge=1, description="Blockchain event polling interval in seconds"
    )
    # Payout wallet (optional, defaults to wallet_address)
    payout_wallet_address: str | None = None

    # Deposit levels (USDT amounts)
    # NOTE: Values must match app/services/deposit_validation_service.py and bot/utils/constants.py
    deposit_level_1: float = Field(
        default=10.0, gt=0, description="Deposit level 1 amount"
    )
    deposit_level_2: float = Field(
        default=50.0, gt=0, description="Deposit level 2 amount"
    )
    deposit_level_3: float = Field(
        default=100.0, gt=0, description="Deposit level 3 amount"
    )
    deposit_level_4: float = Field(
        default=150.0, gt=0, description="Deposit level 4 amount"
    )
    deposit_level_5: float = Field(
        default=300.0, gt=0, description="Deposit level 5 amount"
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
    health_check_port: int = Field(
        default=8080, ge=1, le=65535, description="Health check HTTP server port"
    )

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

    # Blockchain maintenance mode (R7-5)
    blockchain_maintenance_mode: bool = Field(
        default=False,
        description="Blockchain maintenance mode flag"
    )

    # R17-3: Emergency stop flags
    emergency_stop_withdrawals: bool = Field(
        default=False,
        description="Emergency stop for all withdrawals"
    )
    emergency_stop_roi: bool = Field(
        default=False,
        description="Emergency stop for all ROI accrual calculations"
    )

    # R18-4: Dual control settings
    dual_control_withdrawal_threshold: float = Field(
        default=1000.0,
        gt=0,
        description="Withdrawal amount threshold requiring dual control (USDT)"
    )
    dual_control_escrow_expiry_hours: int = Field(
        default=24,
        gt=0,
        description="Escrow expiry time in hours"
    )

    # R18-4: Admin operation limits
    admin_max_withdrawals_per_day: int = Field(
        default=50,
        gt=0,
        description="Maximum withdrawals per day per admin"
    )
    admin_max_withdrawal_amount_per_day: float = Field(
        default=50000.0,
        gt=0,
        description="Maximum total withdrawal amount per day per admin (USDT)"
    )
    admin_max_balance_adjustments_per_week: int = Field(
        default=20,
        gt=0,
        description="Maximum balance adjustments per week per admin"
    )
    emergency_stop_deposits: bool = Field(
        default=False,
        description="Emergency stop for all new deposits"
    )

    # R10-3: Admin security monitor thresholds
    admin_max_bans_per_hour: int = Field(
        default=20,
        gt=0,
        description="Maximum bans per hour before admin is flagged"
    )
    admin_max_terminations_per_hour: int = Field(
        default=20,
        gt=0,
        description="Maximum terminations per hour before admin is flagged"
    )
    admin_max_withdrawal_approvals_per_hour: int = Field(
        default=50,
        gt=0,
        description="Maximum withdrawal approvals per hour"
    )
    admin_max_creations_per_day: int = Field(
        default=5,
        gt=0,
        description="Maximum admin creations per day"
    )
    admin_max_deletions_per_day: int = Field(
        default=5,
        gt=0,
        description="Maximum admin deletions per day"
    )
    admin_max_large_withdrawal_approvals_per_hour: int = Field(
        default=10,
        gt=0,
        description="Maximum large (>$1000) withdrawal approvals per hour"
    )
    admin_large_withdrawal_threshold: float = Field(
        default=1000.0,
        gt=0,
        description="Threshold for 'large' withdrawal (USDT)"
    )

    # R18-1: Dust attack protection
    minimum_deposit_amount: float = Field(
        default=10.0,
        gt=0,
        description="Minimum deposit amount to prevent dust attacks (USDT)"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode='after')
    def set_rpc_defaults(self) -> 'Settings':
        """Set default RPC URLs if not provided."""
        if not self.rpc_quicknode_http:
            self.rpc_quicknode_http = self.rpc_url
        return self

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
            # Check for common insecure patterns (exact matches only)
            # Parse URL to check username:password pairs
            try:
                from urllib.parse import urlparse, unquote
                parsed = urlparse(self.database_url)
                if parsed.password:
                    # Decode URL-encoded password
                    password = unquote(parsed.password)
                    password_lower = password.lower()
                    username = unquote(parsed.username or '')
                    username_lower = username.lower() if username else ''
                    # Check for exact insecure password patterns (exact match only)
                    insecure_passwords = ['password', 'changeme', 'admin', 'root', '']
                    # Check for username == password (common insecure pattern)
                    if password_lower in insecure_passwords:
                        # Only warn, don't block startup - admin can fix via .env
                        logger.warning(
                            f'DATABASE_URL uses insecure password "{password_lower}". '
                            'Please change it in .env file for production security.'
                        )
                    elif username_lower and password_lower == username_lower:
                        # Only warn, don't block startup
                        logger.warning(
                            'DATABASE_URL password is the same as username. '
                            'Please change it in .env file for production security.'
                        )
            except (AttributeError, ImportError, Exception) as e:
                # If parsing fails, skip validation (better than blocking startup)
                logger.warning(
                    f'Could not parse DATABASE_URL for password validation: {e}. '
                    'Skipping insecure password check.'
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
