"""
Unit tests for Settings validation.

Tests Pydantic validators and production mode checks.
"""

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


class TestTelegramTokenValidation:
    """Test Telegram bot token validation."""
    
    def test_valid_token_format(self, monkeypatch):
        """Test valid Telegram token format."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.telegram_bot_token == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
    
    def test_invalid_token_format(self, monkeypatch):
        """Test invalid Telegram token format."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "invalid_token")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        with pytest.raises(ValidationError, match="Invalid Telegram bot token format"):
            Settings()


class TestWalletAddressValidation:
    """Test wallet address validation."""
    
    def test_valid_wallet_address(self, monkeypatch):
        """Test valid wallet address format."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.wallet_address.startswith("0x")
        assert len(settings.wallet_address) == 42
    
    @pytest.mark.parametrize("invalid_address", [
        "742d35Cc6634C0532925a3b844Bc9e7595f0bEb",  # Missing 0x
        "0x742d35Cc6634C0532925a3b844Bc9e7595f0b",  # Too short
        "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEbb",  # Too long
        "0xGGGd35Cc6634C0532925a3b844Bc9e7595f0bEb",  # Invalid hex
    ])
    def test_invalid_wallet_address(self, invalid_address, monkeypatch):
        """Test invalid wallet address formats."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", invalid_address)
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        with pytest.raises(ValidationError, match="Invalid"):
            Settings()


class TestDatabaseURLValidation:
    """Test database URL validation."""
    
    def test_valid_database_url(self, monkeypatch):
        """Test valid database URL."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.database_url.startswith("postgresql+asyncpg://")
    
    @pytest.mark.parametrize("invalid_url", [
        "mysql://user:pass@localhost/db",  # Wrong driver
        "postgresql://user:pass@localhost/db",  # Missing asyncpg
        "sqlite:///db.sqlite",  # Wrong database
    ])
    def test_invalid_database_url(self, invalid_url, monkeypatch):
        """Test invalid database URL."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", invalid_url)
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        with pytest.raises(ValidationError, match="postgresql"):
            Settings()


class TestProductionModeValidation:
    """Test production mode validation."""
    
    def test_production_with_debug_enabled_fails(self, monkeypatch):
        """Test that DEBUG=True fails in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:strongpass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("WALLET_PRIVATE_KEY", "valid_private_key_here")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        with pytest.raises(ValidationError, match="DEBUG must be False"):
            Settings()
    
    def test_production_with_short_secret_key_fails(self, monkeypatch):
        """Test that short SECRET_KEY fails in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:strongpass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("WALLET_PRIVATE_KEY", "valid_private_key_here")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "short")
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        with pytest.raises(ValidationError, match="SECRET_KEY must be at least 32 characters"):
            Settings()
    
    def test_production_with_placeholder_wallet_fails(self, monkeypatch):
        """Test that placeholder wallet private key fails in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:strongpass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("WALLET_PRIVATE_KEY", "your_wallet_private_key_here")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        with pytest.raises(ValidationError, match="WALLET_PRIVATE_KEY must be set with a real value"):
            Settings()
    
    def test_production_with_weak_database_password_fails(self, monkeypatch):
        """Test that weak database password fails in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("WALLET_PRIVATE_KEY", "valid_private_key_here")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        with pytest.raises(ValidationError, match="DATABASE_URL must not use default passwords"):
            Settings()
    
    def test_development_mode_allows_debug(self, monkeypatch):
        """Test that DEBUG=True is allowed in development."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.environment == "development"
        assert settings.debug is True


class TestAdminIDsParsing:
    """Test admin IDs parsing."""
    
    def test_parse_single_admin_id(self, monkeypatch):
        """Test parsing single admin ID."""
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "123456789")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.get_admin_ids() == [123456789]
    
    def test_parse_multiple_admin_ids(self, monkeypatch):
        """Test parsing multiple admin IDs."""
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "123456789,987654321,111222333")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.get_admin_ids() == [123456789, 987654321, 111222333]
    
    def test_parse_admin_ids_with_spaces(self, monkeypatch):
        """Test parsing admin IDs with spaces."""
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", " 123456789 , 987654321 , 111222333 ")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.get_admin_ids() == [123456789, 987654321, 111222333]
    
    def test_empty_admin_ids(self, monkeypatch):
        """Test empty admin IDs."""
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
        monkeypatch.setenv("WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        monkeypatch.setenv("SYSTEM_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEc")
        monkeypatch.setenv("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        monkeypatch.setenv("RPC_URL", "https://bsc-dataseed.binance.org/")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("ENCRYPTION_KEY", "b" * 32)
        
        settings = Settings()
        assert settings.get_admin_ids() == []
