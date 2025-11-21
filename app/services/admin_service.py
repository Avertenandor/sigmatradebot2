"""
Admin service.

Handles admin authentication and session management.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.admin_session import AdminSession
from app.repositories.admin_repository import AdminRepository
from app.repositories.admin_session_repository import (
    AdminSessionRepository,
)

# Admin session configuration
SESSION_DURATION_HOURS = 24
MASTER_KEY_LENGTH = 32  # 32 bytes = 256 bits

# Admin login rate limiting
ADMIN_LOGIN_MAX_ATTEMPTS = 5
ADMIN_LOGIN_WINDOW_SECONDS = 3600  # 1 hour


class AdminService:
    """Admin service for authentication and session management."""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Any | None = None,
    ) -> None:
        """
        Initialize admin service.

        Args:
            session: Database session
            redis_client: Optional Redis client for rate limiting
        """
        self.session = session
        self.admin_repo = AdminRepository(session)
        self.session_repo = AdminSessionRepository(session)
        self.redis_client = redis_client

    @staticmethod
    def generate_master_key() -> str:
        """
        Generate random master key.

        Returns:
            Hex-encoded master key
        """
        return secrets.token_hex(MASTER_KEY_LENGTH)

    @staticmethod
    def hash_master_key(master_key: str) -> str:
        """
        Hash master key using bcrypt.

        Args:
            master_key: Plain master key

        Returns:
            Hashed master key
        """
        return bcrypt.hashpw(
            master_key.encode(), bcrypt.gensalt()
        ).decode()

    @staticmethod
    def verify_master_key(
        plain_key: str, hashed_key: str
    ) -> bool:
        """
        Verify master key against hash.

        Args:
            plain_key: Plain master key
            hashed_key: Hashed master key

        Returns:
            True if match
        """
        return bcrypt.checkpw(
            plain_key.encode(), hashed_key.encode()
        )

    @staticmethod
    def generate_session_token() -> str:
        """
        Generate random session token.

        Returns:
            Hex-encoded session token
        """
        return secrets.token_urlsafe(32)

    async def create_admin(
        self,
        telegram_id: int,
        role: str,
        created_by: int,
        username: str | None = None,
    ) -> tuple[Admin | None, str | None, str | None]:
        """
        Create new admin with master key.

        Args:
            telegram_id: Telegram user ID
            role: admin or super_admin
            created_by: Creator admin ID
            username: Telegram username (optional)

        Returns:
            Tuple of (admin, master_key, error_message)
        """
        # Check if admin exists
        existing = await self.admin_repo.find_by(
            telegram_id=telegram_id
        )

        if existing:
            return (
                None,
                None,
                "Админ с таким Telegram ID уже существует",
            )

        # Generate and hash master key
        plain_master_key = self.generate_master_key()
        hashed_master_key = self.hash_master_key(plain_master_key)

        # Create admin
        admin = await self.admin_repo.create(
            telegram_id=telegram_id,
            username=username,
            role=role,
            master_key=hashed_master_key,
            created_by=created_by,
        )

        await self.session.commit()

        logger.info(
            "Admin created",
            extra={
                "admin_id": admin.id,
                "telegram_id": telegram_id,
                "role": role,
                "created_by": created_by,
            },
        )

        return admin, plain_master_key, None

    async def login(
        self,
        telegram_id: int,
        master_key: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[AdminSession | None, Admin | None, str | None]:
        """
        Authenticate admin and create session.

        Args:
            telegram_id: Telegram user ID
            master_key: Plain master key
            ip_address: IP address (optional)
            user_agent: User agent string (optional)

        Returns:
            Tuple of (session, admin, error_message)
        """
        # Find admin
        admins = await self.admin_repo.find_by(
            telegram_id=telegram_id
        )

        if not admins:
            logger.warning(
                "Admin not found", extra={"telegram_id": telegram_id}
            )
            return None, None, "Администратор не найден"

        admin = admins[0]

        if not admin.master_key:
            return None, None, "Мастер-ключ не установлен"

        # Verify master key
        if not self.verify_master_key(
            master_key, admin.master_key
        ):
            # Track failed login attempt
            await self._track_failed_login(telegram_id)
            
            logger.warning(
                "Invalid master key attempt",
                extra={
                    "admin_id": admin.id,
                    "telegram_id": telegram_id,
                },
            )
            return None, None, "Неверный мастер-ключ"

        # Clear failed login attempts on successful login
        await self._clear_failed_login_attempts(telegram_id)

        # Deactivate all existing sessions
        await self.session_repo.deactivate_all_for_admin(admin.id)

        # Create new session
        session_token = self.generate_session_token()
        expires_at = datetime.now(UTC) + timedelta(
            hours=SESSION_DURATION_HOURS
        )

        session = await self.session_repo.create(
            admin_id=admin.id,
            session_token=session_token,
            is_active=True,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )

        await self.session.commit()

        logger.info(
            "Admin logged in",
            extra={
                "admin_id": admin.id,
                "telegram_id": telegram_id,
                "session_id": session.id,
            },
        )

        return session, admin, None

    async def logout(self, session_token: str) -> bool:
        """
        Logout admin (deactivate session).

        Args:
            session_token: Session token

        Returns:
            Success flag
        """
        sessions = await self.session_repo.find_by(
            session_token=session_token, is_active=True
        )

        if not sessions:
            return False

        session = sessions[0]
        await self.session_repo.update(
            session.id, is_active=False
        )

        await self.session.commit()

        logger.info(
            "Admin logged out",
            extra={"session_token": session_token},
        )

        return True

    async def validate_session(
        self, session_token: str
    ) -> tuple[Admin | None, AdminSession | None, str | None]:
        """
        Validate session and update activity.

        Args:
            session_token: Session token

        Returns:
            Tuple of (admin, session, error_message)
        """
        sessions = await self.session_repo.find_by(
            session_token=session_token, is_active=True
        )

        if not sessions:
            return None, None, "Сессия не найдена"

        session = sessions[0]

        # Check if expired
        if session.is_expired:
            await self.session_repo.update(
                session.id, is_active=False
            )
            await self.session.commit()

            logger.info(
                "Session expired",
                extra={"session_id": session.id},
            )
            return None, None, "Сессия истекла. Войдите заново"

        # Check if inactive (no activity for 15 minutes)
        if session.is_inactive:
            await self.session_repo.update(
                session.id, is_active=False
            )
            await self.session.commit()

            logger.info(
                "Session inactive (15 minutes)",
                extra={"session_id": session.id},
            )
            return (
                None,
                None,
                "Сессия неактивна (бездействие более 15 минут). "
                "Войдите заново",
            )

        # Update activity
        await self.session_repo.update(
            session.id, last_activity=datetime.now(UTC)
        )

        # Load admin
        admin = await self.admin_repo.get_by_id(session.admin_id)

        if not admin:
            return None, None, "Admin not found"

        # R10-3: Check if admin is blocked
        if admin.is_blocked:
            logger.warning(
                f"R10-3: Blocked admin {admin.id} attempted to use session "
                f"{session_token[:8]}..."
            )
            # Invalidate session
            await self.session_repo.delete(session.id)
            await self.session.commit()
            return None, None, "Admin account is blocked"

        await self.session.commit()

        return admin, session, None

    async def get_admin_by_telegram_id(
        self, telegram_id: int
    ) -> Admin | None:
        """
        Get admin by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Admin or None
        """
        admins = await self.admin_repo.find_by(
            telegram_id=telegram_id
        )
        return admins[0] if admins else None

    async def list_all_admins(self) -> list[Admin]:
        """
        List all admins.

        Returns:
            List of all admins
        """
        return await self.admin_repo.find_all()

    async def get_all_admins(self) -> list[Admin]:
        """
        Get all admins (alias).

        Returns:
            List of all admins
        """
        return await self.list_all_admins()

    async def get_admin_by_id(self, admin_id: int) -> Admin | None:
        """
        Get admin by ID.

        Args:
            admin_id: Admin ID

        Returns:
            Admin or None
        """
        return await self.admin_repo.get_by_id(admin_id)

    async def delete_admin(self, admin_id: int) -> bool:
        """
        Delete admin.

        Args:
            admin_id: Admin ID

        Returns:
            Success flag
        """
        admin = await self.admin_repo.get_by_id(admin_id)

        if not admin:
            return False

        # Deactivate all sessions
        await self.session_repo.deactivate_all_for_admin(admin_id)

        # Delete admin
        await self.admin_repo.delete(admin_id)
        await self.session.commit()

        logger.info(
            "Admin deleted", extra={"admin_id": admin_id}
        )

        return True

    async def _track_failed_login(self, telegram_id: int) -> None:
        """
        Track failed login attempt and block if limit exceeded.

        Args:
            telegram_id: Telegram user ID
        """
        if not self.redis_client:
            return  # No Redis, skip rate limiting

        try:
            key = f"admin_login_attempts:{telegram_id}"
            
            # Get current count
            count_str = await self.redis_client.get(key)
            count = int(count_str) if count_str else 0
            
            # Increment
            count += 1
            await self.redis_client.setex(
                key, ADMIN_LOGIN_WINDOW_SECONDS, str(count)
            )
            
            # Check if limit exceeded
            if count >= ADMIN_LOGIN_MAX_ATTEMPTS:
                from app.utils.security_logging import log_security_event

                log_security_event(
                    "Admin login rate limit exceeded",
                    {
                        "telegram_id": telegram_id,
                        "action_type": "ADMIN_LOGIN_BRUTE_FORCE",
                        "attempts": count,
                        "limit": ADMIN_LOGIN_MAX_ATTEMPTS,
                    }
                )
                
                # Block the Telegram ID
                await self._block_telegram_id_for_failed_logins(telegram_id)
                
        except Exception as e:
            # R11-2: Redis failed, continue without rate limiting
            logger.warning(
                f"R11-2: Redis error tracking failed login for {telegram_id}: {e}. "
                "Continuing without rate limiting (degraded mode)."
            )

    async def _clear_failed_login_attempts(self, telegram_id: int) -> None:
        """
        Clear failed login attempts on successful login.

        Args:
            telegram_id: Telegram user ID
        """
        if not self.redis_client:
            return

        try:
            key = f"admin_login_attempts:{telegram_id}"
            await self.redis_client.delete(key)
        except Exception as e:
            # R11-2: Redis failed, continue without clearing
            logger.warning(
                f"R11-2: Redis error clearing failed login attempts for {telegram_id}: {e}. "
                "Continuing without clearing (degraded mode)."
            )

    async def _block_telegram_id_for_failed_logins(
        self, telegram_id: int
    ) -> None:
        """
        Block Telegram ID after too many failed login attempts.

        Args:
            telegram_id: Telegram user ID to block
        """
        try:
            from app.models.blacklist import BlacklistActionType
            from app.services.blacklist_service import BlacklistService

            # Add to blacklist
            blacklist_service = BlacklistService(self.session)
            await blacklist_service.add_to_blacklist(
                telegram_id=telegram_id,
                reason="Too many failed admin login attempts",
                added_by_admin_id=None,  # System action
                action_type=BlacklistActionType.BLOCKED,
            )

            # If user exists, ban them
            from app.repositories.user_repository import UserRepository

            user_repo = UserRepository(self.session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user:
                user.is_banned = True
                await self.session.flush()

            await self.session.commit()

            # Notify all super_admins
            await self._notify_super_admins_of_block(telegram_id)

            from app.utils.security_logging import log_security_event

            log_security_event(
                "Telegram ID blocked due to failed admin login attempts",
                {
                    "telegram_id": telegram_id,
                    "action_type": "AUTO_BLOCKED",
                    "reason": "Too many failed admin login attempts",
                }
            )

            # Send security notification
            from app.utils.admin_notifications import notify_security_event

            await notify_security_event(
                "Admin Login Brute Force Detected",
                f"Telegram ID {telegram_id} blocked after "
                f"{ADMIN_LOGIN_MAX_ATTEMPTS} failed login attempts",
                priority="critical",
            )

        except Exception as e:
            logger.error(
                f"Error blocking Telegram ID for failed logins: {e}"
            )
            await self.session.rollback()

    async def _notify_super_admins_of_block(
        self, telegram_id: int
    ) -> None:
        """
        Notify all super_admins about automatic block.

        Args:
            telegram_id: Blocked Telegram ID
        """
        try:
            from app.config.settings import settings
            from aiogram import Bot

            # Get all super_admins
            super_admins = [
                a for a in await self.list_all_admins()
                if a.is_super_admin
            ]

            if not super_admins:
                return

            bot = Bot(token=settings.telegram_bot_token)
            notification_text = (
                f"🚨 **Автоматическая блокировка**\n\n"
                f"Telegram ID `{telegram_id}` был автоматически "
                f"заблокирован из-за превышения лимита неуспешных "
                f"попыток входа в админ-панель.\n\n"
                f"Лимит: {ADMIN_LOGIN_MAX_ATTEMPTS} попыток за "
                f"{ADMIN_LOGIN_WINDOW_SECONDS // 60} минут"
            )

            for super_admin in super_admins:
                try:
                    await bot.send_message(
                        chat_id=super_admin.telegram_id,
                        text=notification_text,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to notify super_admin "
                        f"{super_admin.id}: {e}"
                    )

            await bot.session.close()

        except Exception as e:
            logger.error(f"Error notifying super_admins: {e}")
