"""
Settings Service.

Manages system settings stored in database with Redis caching.
"""

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting
from app.repositories.system_setting_repository import (
    SystemSettingRepository,
)

if TYPE_CHECKING:
    import redis.asyncio as redis  # type: ignore


class SettingsService:
    """
    Service for managing system settings.

    Features:
    - Database-backed settings
    - Redis caching with TTL
    - Type conversion helpers
    - Default values
    """

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Optional[Any] = None,  # Redis client for caching
        cache_ttl: int = 300,  # 5 minutes
    ) -> None:
        """
        Initialize settings service.

        Args:
            session: Database session
            redis_client: Redis client for caching (optional)
            cache_ttl: Cache TTL in seconds
        """
        self.session = session
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.repository = SystemSettingRepository(session)

        # Cache key prefix
        self.cache_prefix = "settings:"

    async def get(
        self,
        key: str,
        default: Any = None,
        use_cache: bool = True,
    ) -> Optional[str]:
        """
        Get setting value.

        Args:
            key: Setting key
            default: Default value if not found
            use_cache: Whether to use Redis cache

        Returns:
            Setting value or default
        """
        # Try cache first
        if use_cache and self.redis_client:
            try:
                cached_value = await self.redis_client.get(
                    f"{self.cache_prefix}{key}"
                )
                if cached_value is not None:
                    return cached_value.decode("utf-8")
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")

        # Get from database
        setting = await self.repository.get_by_key(key)

        if setting:
            value = setting.value

            # Update cache
            if use_cache and self.redis_client:
                try:
                    await self.redis_client.setex(
                        f"{self.cache_prefix}{key}",
                        self.cache_ttl,
                        value,
                    )
                except Exception as e:
                    logger.warning(f"Redis cache set error: {e}")

            return value

        return default

    async def get_int(
        self,
        key: str,
        default: int = 0,
    ) -> int:
        """
        Get setting as integer.

        Args:
            key: Setting key
            default: Default value

        Returns:
            Integer value
        """
        value = await self.get(key)

        if value is None:
            return default

        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid int value for {key}: {value}")
            return default

    async def get_float(
        self,
        key: str,
        default: float = 0.0,
    ) -> float:
        """
        Get setting as float.

        Args:
            key: Setting key
            default: Default value

        Returns:
            Float value
        """
        value = await self.get(key)

        if value is None:
            return default

        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid float value for {key}: {value}")
            return default

    async def get_bool(
        self,
        key: str,
        default: bool = False,
    ) -> bool:
        """
        Get setting as boolean.

        Args:
            key: Setting key
            default: Default value

        Returns:
            Boolean value
        """
        value = await self.get(key)

        if value is None:
            return default

        # Value is already string from DB, parse it
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off"):
            return False

        return bool(value)

    async def set(
        self,
        key: str,
        value: Any,
        description: Optional[str] = None,
    ) -> SystemSetting:
        """
        Set setting value.

        Args:
            key: Setting key
            value: Setting value
            description: Optional description

        Returns:
            SystemSetting instance
        """
        # Convert value to string
        value_str = str(value)

        # Check if exists
        existing = await self.repository.get_by_key(key)

        if existing:
            # Update
            update_data = {"value": value_str}
            if description:
                update_data["description"] = description
            await self.repository.update(existing.id, **update_data)
            setting = existing
        else:
            # Create
            setting = await self.repository.create(
                key=key,
                value=value_str,
                description=description or f"Setting: {key}",
            )

        # Invalidate cache
        if self.redis_client:
            try:
                await self.redis_client.delete(f"{self.cache_prefix}{key}")
            except Exception as e:
                logger.warning(f"Redis cache delete error: {e}")

        logger.info(f"Setting updated: {key} = {value_str}")

        return setting

    async def delete(self, key: str) -> bool:
        """
        Delete setting.

        Args:
            key: Setting key

        Returns:
            True if deleted
        """
        setting = await self.repository.get_by_key(key)

        if not setting:
            return False

        # SystemSetting uses 'key' as primary key, not 'id'
        await self.repository.delete(setting.key)

        # Invalidate cache
        if self.redis_client:
            try:
                await self.redis_client.delete(f"{self.cache_prefix}{key}")
            except Exception as e:
                logger.warning(f"Redis cache delete error: {e}")

        logger.info(f"Setting deleted: {key}")

        return True

    async def get_all(self) -> list[SystemSetting]:
        """
        Get all settings.

        Returns:
            List of SystemSetting instances
        """
        return await self.repository.get_all()

    async def clear_cache(self, key: Optional[str] = None) -> None:
        """
        Clear settings cache.

        Args:
            key: Specific key to clear, or None for all
        """
        if not self.redis_client:
            return

        try:
            if key:
                await self.redis_client.delete(f"{self.cache_prefix}{key}")
            else:
                # Clear all settings cache
                pattern = f"{self.cache_prefix}*"
                cursor = 0

                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor=cursor,
                        match=pattern,
                        count=100,
                    )

                    if keys:
                        await self.redis_client.delete(*keys)

                    if cursor == 0:
                        break

            logger.info("Settings cache cleared")
        except Exception as e:
            logger.error(f"Error clearing settings cache: {e}")


# Singleton management (optional, for global access)
_settings_service: Optional[SettingsService] = None


def init_settings_service(
    session: AsyncSession,
    redis_client: Optional[redis.Redis] = None,
) -> SettingsService:
    """Initialize settings service singleton."""
    global _settings_service

    _settings_service = SettingsService(
        session=session,
        redis_client=redis_client,
    )

    return _settings_service


def get_settings_service() -> Optional[SettingsService]:
    """Get settings service singleton."""
    return _settings_service
