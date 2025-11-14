"""
Admin service.

Handles admin authentication and session management.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from loguru import logger
from sqlalchemy import select
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


class AdminService:
    """Admin service for authentication and session management."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize admin service."""
        self.session = session
        self.admin_repo = AdminRepository(session)
        self.session_repo = AdminSessionRepository(session)

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
        username: Optional[str] = None,
    ) -> tuple[Optional[Admin], Optional[str], Optional[str]]:
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
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[Optional[AdminSession], Optional[Admin], Optional[str]]:
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
            logger.warning(
                "Invalid master key attempt",
                extra={
                    "admin_id": admin.id,
                    "telegram_id": telegram_id,
                },
            )
            return None, None, "Неверный мастер-ключ"

        # Deactivate all existing sessions
        await self.session_repo.deactivate_all_for_admin(admin.id)

        # Create new session
        session_token = self.generate_session_token()
        expires_at = datetime.utcnow() + timedelta(
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
    ) -> tuple[Optional[Admin], Optional[AdminSession], Optional[str]]:
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

        # Update activity
        await self.session_repo.update(
            session.id, last_activity_at=datetime.utcnow()
        )

        # Load admin
        admin = await self.admin_repo.get_by_id(session.admin_id)

        await self.session.commit()

        return admin, session, None

    async def get_admin_by_telegram_id(
        self, telegram_id: int
    ) -> Optional[Admin]:
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
