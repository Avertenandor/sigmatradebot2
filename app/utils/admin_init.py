"""
Admin initialization utility.

Creates default super admin on first startup.
"""


from aiogram import Bot
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.repositories.admin_repository import AdminRepository

# Default super admin Telegram ID
DEFAULT_SUPER_ADMIN_TELEGRAM_ID = 1040687384


async def ensure_default_super_admin(
    session: AsyncSession,
    bot: Bot | None = None,
) -> None:
    """
    Ensure default super admin exists.

    Creates super admin with full permissions if not exists.
    Updates username from Telegram API if bot is provided.

    Args:
        session: Database session
        bot: Optional bot instance to fetch user info from Telegram
    """
    admin_repo = AdminRepository(session)

    # Check if super admin already exists
    existing_admin = await admin_repo.get_by_telegram_id(
        DEFAULT_SUPER_ADMIN_TELEGRAM_ID
    )

    # Try to get username from Telegram API if bot is provided
    username = None
    if bot:
        try:
            user_info = await bot.get_chat(DEFAULT_SUPER_ADMIN_TELEGRAM_ID)
            username = getattr(user_info, 'username', None)
            logger.debug(
                f"Fetched username for admin "
                f"{DEFAULT_SUPER_ADMIN_TELEGRAM_ID}: {username}"
            )
        except Exception as e:
            logger.warning(
                f"Could not fetch user info from Telegram API: {e}"
            )

    if existing_admin:
        # Update role to super_admin if not already
        updated = False
        if existing_admin.role != "super_admin":
            existing_admin.role = "super_admin"
            updated = True

        # Update username if available and different
        if username and existing_admin.username != username:
            existing_admin.username = username
            updated = True

        if updated:
            await session.commit()
            logger.info(
                f"Updated admin {DEFAULT_SUPER_ADMIN_TELEGRAM_ID} to "
                f"super_admin"
                f"{f' with username @{username}' if username else ''}"
            )
        else:
            logger.debug(
                f"Super admin {DEFAULT_SUPER_ADMIN_TELEGRAM_ID} already exists"
            )
        return

    # Create new super admin
    new_admin = Admin(
        telegram_id=DEFAULT_SUPER_ADMIN_TELEGRAM_ID,
        username=username,
        role="super_admin",
        master_key=None,  # Can be set later via admin interface
        created_by=None,  # First admin, no creator
    )

    session.add(new_admin)
    await session.commit()

    logger.info(
        f"Created default super admin with Telegram ID: "
        f"{DEFAULT_SUPER_ADMIN_TELEGRAM_ID}"
        f"{f' (@{username})' if username else ''}"
    )
