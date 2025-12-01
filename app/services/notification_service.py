"""
Notification service (+ PART5 multimedia support).

Sends notifications to users via Telegram.
"""

from typing import Any

from aiogram import Bot
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.failed_notification import FailedNotification
from app.repositories.admin_repository import AdminRepository
from app.repositories.failed_notification_repository import (
    FailedNotificationRepository,
)
from app.repositories.support_ticket_repository import SupportTicketRepository


class NotificationService:
    """
    Notification service.

    Handles Telegram notifications with multimedia support (PART5).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize notification service."""
        self.session = session
        self.failed_repo = FailedNotificationRepository(session)
        self.admin_repo = AdminRepository(session)
        self.ticket_repo = SupportTicketRepository(session)

    async def send_notification(
        self,
        bot: Bot,
        user_telegram_id: int,
        message: str,
        critical: bool = False,
        redis_client: Any | None = None,
    ) -> bool:
        """
        Send text notification.

        R11-3: If Redis is unavailable, writes to PostgreSQL fallback queue.

        Args:
            bot: Bot instance
            user_telegram_id: Telegram user ID
            message: Message text
            critical: Mark as critical
            redis_client: Optional Redis client for checking availability

        Returns:
            True if sent successfully or queued to fallback
        """
        # R11-3: Check if Redis is available
        redis_available = False
        if redis_client is not None:
            try:
                await redis_client.ping()
                redis_available = True
            except Exception:
                redis_available = False
                logger.warning(
                    "R11-3: Redis unavailable, will use PostgreSQL fallback"
                )

        # R11-3: If Redis is unavailable, write to PostgreSQL fallback
        if not redis_available:
            try:
                from app.models.notification_queue_fallback import (
                    NotificationQueueFallback,
                )
                from app.repositories.user_repository import UserRepository

                user_repo = UserRepository(self.session)
                user = await user_repo.get_by_telegram_id(user_telegram_id)

                if user:
                    # Create fallback queue entry
                    fallback_entry = NotificationQueueFallback(
                        user_id=user.id,
                        notification_type="text",
                        payload={
                            "message": message,
                            "critical": critical,
                        },
                        priority=100 if critical else 0,
                    )
                    self.session.add(fallback_entry)
                    await self.session.flush()

                    logger.info(
                        f"R11-3: Notification queued to PostgreSQL fallback "
                        f"for user {user_telegram_id} (user_id={user.id})"
                    )
                    return True
                else:
                    logger.warning(
                        f"R11-3: Cannot queue notification for unknown user "
                        f"{user_telegram_id}"
                    )
            except Exception as fallback_error:
                logger.error(
                    f"R11-3: Failed to write to PostgreSQL fallback: {fallback_error}",
                    exc_info=True,
                )

        try:
            await bot.send_message(
                chat_id=user_telegram_id, text=message
            )
            
            # R8-2: If message sent successfully, check if user was previously blocked
            # and reset the flag (user unblocked the bot)
            try:
                from app.repositories.user_repository import UserRepository
                user_repo = UserRepository(self.session)
                user = await user_repo.get_by_telegram_id(user_telegram_id)
                if user and hasattr(user, 'bot_blocked') and user.bot_blocked:
                    # User unblocked the bot - reset flag
                    await user_repo.update(user.id, bot_blocked=False)
                    logger.info(
                        f"User {user_telegram_id} unblocked the bot, flag reset"
                    )
            except Exception as reset_error:
                # Don't fail notification if flag reset fails
                logger.warning(f"Failed to reset bot_blocked flag: {reset_error}")
            
            return True
        except Exception as e:
            # R8-2: Improved 403 error handling with specific TelegramAPIError check
            from aiogram.exceptions import TelegramAPIError
            from datetime import UTC, datetime
            
            # Check for specific "bot was blocked by the user" error
            is_bot_blocked = False
            if isinstance(e, TelegramAPIError):
                # Check error code and message
                if e.error_code == 403:
                    error_message = str(e).lower()
                    if "bot was blocked by the user" in error_message or "blocked" in error_message:
                        is_bot_blocked = True
            else:
                # Fallback for non-TelegramAPIError exceptions
                error_str = str(e).lower()
                if "403" in error_str or "forbidden" in error_str:
                    if "blocked" in error_str or "bot was blocked" in error_str:
                        is_bot_blocked = True
            
            if is_bot_blocked:
                logger.warning(
                    f"Bot blocked by user {user_telegram_id}",
                    extra={"user_id": user_telegram_id},
                )
                
                # Mark user as having blocked bot
                try:
                    from app.repositories.user_repository import UserRepository
                    
                    user_repo = UserRepository(self.session)
                    user = await user_repo.find_by_telegram_id(user_telegram_id)
                    if user and not user.bot_blocked:
                        await user_repo.update(
                            user.id,
                            bot_blocked=True,
                            bot_blocked_at=datetime.now(UTC),
                        )
                        await self.session.commit()
                        logger.info(
                            f"Marked user {user_telegram_id} as bot_blocked"
                        )
                except Exception as update_error:
                    logger.error(
                        f"Failed to mark user as bot_blocked: {update_error}"
                    )
                
                # Don't save to failed notifications for blocked users
                # (they won't receive it anyway)
                return False
            
            logger.error(
                f"Failed to send notification: {e}",
                extra={"user_id": user_telegram_id},
            )

            # Save to failed notifications (PART5) for other errors
            await self._save_failed_notification(
                user_telegram_id,
                "text_message",
                message,
                str(e),
                critical,
            )
            return False

    async def send_photo(
        self,
        bot: Bot,
        user_telegram_id: int,
        file_id: str,
        caption: str | None = None,
    ) -> bool:
        """
        Send photo notification (PART5 multimedia).

        Args:
            bot: Bot instance
            user_telegram_id: Telegram user ID
            file_id: Telegram file ID
            caption: Photo caption

        Returns:
            True if sent successfully
        """
        try:
            await bot.send_photo(
                chat_id=user_telegram_id,
                photo=file_id,
                caption=caption,
            )
            return True
        except Exception as e:
            await self._save_failed_notification(
                user_telegram_id,
                "photo",
                caption or "",
                str(e),
                metadata={"file_id": file_id},
            )
            return False

    async def _save_failed_notification(
        self,
        user_telegram_id: int,
        notification_type: str,
        message: str,
        error: str,
        critical: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> FailedNotification:
        """Save failed notification for retry (PART5)."""
        return await self.failed_repo.create(
            user_telegram_id=user_telegram_id,
            notification_type=notification_type,
            message=message,
            last_error=error,
            critical=critical,
            notification_metadata=metadata,
        )

    async def notify_admins_new_ticket(
        self, bot: Bot, ticket_id: int
    ) -> None:
        """
        Notify all admins about new support ticket.

        Args:
            bot: Bot instance
            ticket_id: Support ticket ID
        """
        # Get ticket details
        ticket = await self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            logger.error(
                "Ticket not found for admin notification",
                extra={"ticket_id": ticket_id},
            )
            return

        # Get all admins
        all_admins = await self.admin_repo.find_by()

        if not all_admins:
            logger.warning("No admins found to notify about new ticket")
            return

        # Build notification message
        message = f"""
🆕 **Новое обращение в поддержку**

📋 Тикет #{ticket_id}
👤 Пользователь ID: {ticket.user_id}
📂 Категория: {ticket.category}
🕐 Время создания: {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')}

Перейдите в админ-панель для обработки.
        """.strip()

        # Send to all admins
        for admin in all_admins:
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=message,
                    parse_mode="Markdown",
                )
                logger.info(
                    "Admin notified about new ticket",
                    extra={
                        "admin_id": admin.id,
                        "ticket_id": ticket_id,
                    },
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify admin about ticket: {e}",
                    extra={
                        "admin_id": admin.id,
                        "ticket_id": ticket_id,
                    },
                )
                await self._save_failed_notification(
                    admin.telegram_id,
                    "admin_notification",
                    message,
                    str(e),
                    critical=True,
                )

    async def notify_admins(
        self,
        bot: Bot,
        message: str,
        critical: bool = False,
    ) -> int:
        """
        Notify all admins with a message.

        Args:
            bot: Bot instance
            message: Message text to send
            critical: Mark as critical notification

        Returns:
            Number of admins successfully notified
        """
        # Get all admins
        all_admins = await self.admin_repo.find_by()

        if not all_admins:
            logger.warning("No admins found to notify")
            return 0

        success_count = 0

        # Send to all admins
        for admin in all_admins:
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=message,
                    parse_mode="Markdown",
                )
                success_count += 1
                logger.info(
                    "Admin notified",
                    extra={
                        "admin_id": admin.id,
                        "telegram_id": admin.telegram_id,
                        "critical": critical,
                    },
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify admin: {e}",
                    extra={
                        "admin_id": admin.id,
                        "telegram_id": admin.telegram_id,
                    },
                )
                await self._save_failed_notification(
                    admin.telegram_id,
                    "admin_notification",
                    message,
                    str(e),
                    critical=critical,
                )

        return success_count

    async def notify_withdrawal_processed(
        self, telegram_id: int, amount: float, tx_hash: str
    ) -> bool:
        """
        Notify user about withdrawal being processed.

        Args:
            telegram_id: User telegram ID
            amount: Withdrawal amount
            tx_hash: Transaction hash

        Returns:
            True if notification sent successfully
        """
        from bot.main import bot_instance
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from app.config.settings import settings

        bot = bot_instance
        should_close = False

        if not bot:
            try:
                bot = Bot(
                    token=settings.telegram_bot_token,
                    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
                )
                should_close = True
            except Exception as e:
                logger.error(f"Failed to create fallback bot instance: {e}")
                return False

        message = (
            f"✅ **Выплата отправлена!**\n\n"
            f"💰 Сумма: {amount:.2f} USDT\n"
            f"🔗 TX: [Посмотреть транзакцию](https://bscscan.com/tx/{tx_hash})\n\n"
            f"🤝 Спасибо за ваше доверие к SigmaTrade!"
        )

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to notify user about withdrawal: {e}",
                extra={"telegram_id": telegram_id},
            )
            return False
        finally:
            if should_close and bot:
                await bot.session.close()

    async def notify_withdrawal_rejected(
        self, telegram_id: int, amount: float
    ) -> bool:
        """
        Notify user about withdrawal being rejected.

        Args:
            telegram_id: User telegram ID
            amount: Withdrawal amount

        Returns:
            True if notification sent successfully
        """
        from bot.main import bot_instance
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from app.config.settings import settings

        bot = bot_instance
        should_close = False

        if not bot:
            try:
                bot = Bot(
                    token=settings.telegram_bot_token,
                    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
                )
                should_close = True
            except Exception as e:
                logger.error(f"Failed to create fallback bot instance: {e}")
                return False

        message = (
            f"❌ **Ваша заявка на вывод средств отклонена**\n\n"
            f"💰 Сумма: {amount:.2f} USDT\n\n"
            f"Для получения дополнительной информации обратитесь в поддержку."
        )

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to notify user about withdrawal rejection: {e}",
                extra={"telegram_id": telegram_id},
            )
            return False
        finally:
            if should_close and bot:
                await bot.session.close()

    async def notify_roi_accrual(
        self,
        telegram_id: int,
        amount: float,
        deposit_level: int,
        roi_progress_percent: float,
    ) -> bool:
        """
        Notify user about ROI accrual.

        Args:
            telegram_id: User telegram ID
            amount: ROI amount accrued
            deposit_level: Deposit level
            roi_progress_percent: Current ROI progress (0-500%)

        Returns:
            True if notification sent successfully
        """
        from bot.main import bot_instance
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from app.config.settings import settings

        bot = bot_instance
        should_close = False

        if not bot:
            try:
                bot = Bot(
                    token=settings.telegram_bot_token,
                    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
                )
                should_close = True
            except Exception as e:
                logger.error(f"Failed to create fallback bot instance: {e}")
                return False

        # Progress bar
        filled = int(roi_progress_percent / 50)  # 10 blocks for 500%
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty

        message = (
            f"💰 *Начислен ROI*\n\n"
            f"📊 Уровень {deposit_level}: *+{amount:.2f} USDT*\n"
            f"📈 Прогресс: {progress_bar} {roi_progress_percent:.1f}%\n\n"
            f"_Баланс обновлён автоматически._"
        )

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to notify user about ROI accrual: {e}",
                extra={"telegram_id": telegram_id},
            )
            return False
        finally:
            if should_close and bot:
                await bot.session.close()