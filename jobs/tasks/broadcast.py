"""Broadcast messaging task."""

import asyncio

from aiogram import Bot
from app.database import async_session_maker
from loguru import logger


async def broadcast_message(
    bot: Bot,
    message_text: str,
    user_ids: list[int] | None = None,
    rate_limit: int = 15,  # messages per second
) -> dict:
    """
    Broadcast message to users.

    Args:
        bot: Bot instance
        message_text: Message to send
        user_ids: List of user IDs (or all if None)
        rate_limit: Max messages per second

    Returns:
        Dict with success/fail counts
    """
    try:
        async with async_session_maker() as session:
            # Get user IDs if not provided
            if user_ids is None:
                from app.repositories.user_repository import UserRepository

                user_repo = UserRepository(session)
                users = await user_repo.get_all_active_users()
                user_ids = [user.telegram_id for user in users]

            logger.info(f"Starting broadcast to {len(user_ids)} users")

            success_count = 0
            fail_count = 0

            # Calculate delay between messages
            delay = 1.0 / rate_limit if rate_limit > 0 else 0

            for user_id in user_ids:
                try:
                    await bot.send_message(user_id, message_text)
                    success_count += 1

                    # Rate limiting
                    if delay > 0:
                        await asyncio.sleep(delay)

                except Exception as e:
                    logger.warning(f"Failed to send to {user_id}: {e}")
                    fail_count += 1

            logger.success(
                f"Broadcast completed: {success_count} sent,"
                    "{fail_count} failed"
            )

            return {
                "total": len(user_ids),
                "success": success_count,
                "failed": fail_count,
            }

    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return {"total": 0, "success": 0, "failed": 0, "error": str(e)}
