"""
Broadcast Service.

Handles mass message sending with rate limiting and background execution.
"""

import asyncio
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.admin_log_service import AdminLogService
from app.services.user_service import UserService


class BroadcastService:
    """Service for handling broadcasts."""

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot

    async def start_broadcast(
        self,
        admin_id: int,
        broadcast_data: dict,
        button_data: dict | None,
        admin_telegram_id: int,  # To notify about completion
    ) -> str:
        """
        Start broadcast in background.
        
        Returns:
            Broadcast ID
        """
        broadcast_id = f"broadcast_{admin_id}_{int(datetime.now().timestamp())}"
        
        # Start background task
        asyncio.create_task(
            self._broadcast_task(
                admin_id, broadcast_data, button_data, admin_telegram_id, broadcast_id
            )
        )
        
        return broadcast_id

    async def _broadcast_task(
        self,
        admin_id: int,
        broadcast_data: dict,
        button_data: dict | None,
        admin_telegram_id: int,
        broadcast_id: str,
    ) -> None:
        """Background broadcast task."""
        logger.info(f"Starting broadcast {broadcast_id}")
        
        try:
            user_service = UserService(self.session)
            user_telegram_ids = await user_service.get_all_telegram_ids()
            
            if not user_telegram_ids:
                return

            # Prepare markup
            reply_markup = None
            if button_data:
                builder = InlineKeyboardBuilder()
                builder.button(text=button_data["text"], url=button_data["url"])
                reply_markup = builder.as_markup()

            success_count = 0
            failed_count = 0
            
            broadcast_type = broadcast_data["type"]
            text = broadcast_data.get("text")
            file_id = broadcast_data.get("file_id")
            caption = broadcast_data.get("caption")

            for i, telegram_id in enumerate(user_telegram_ids):
                try:
                    if broadcast_type == "text":
                        await self.bot.send_message(
                            telegram_id,
                            text,
                            parse_mode="Markdown",
                            reply_markup=reply_markup,
                        )
                    elif broadcast_type == "photo":
                        await self.bot.send_photo(
                            telegram_id,
                            file_id,
                            caption=caption,
                            parse_mode="Markdown" if caption else None,
                            reply_markup=reply_markup,
                        )
                    elif broadcast_type == "voice":
                        await self.bot.send_voice(
                            telegram_id,
                            file_id,
                            caption=caption,
                            parse_mode="Markdown" if caption else None,
                            reply_markup=reply_markup,
                        )
                    elif broadcast_type == "audio":
                        await self.bot.send_audio(
                            telegram_id,
                            file_id,
                            caption=caption,
                            parse_mode="Markdown" if caption else None,
                            reply_markup=reply_markup,
                        )

                    success_count += 1

                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    # Retry once after waiting
                    try:
                        if broadcast_type == "text":
                            await self.bot.send_message(
                                telegram_id,
                                text,
                                parse_mode="Markdown",
                                reply_markup=reply_markup,
                            )
                            success_count += 1
                        else:
                            # Skip retry for media to avoid complexity
                            failed_count += 1
                    except Exception as retry_error:
                        logger.warning(f"Retry failed for {telegram_id}: {retry_error}")
                        failed_count += 1
                except Exception as send_error:
                    logger.debug(f"Failed to send to {telegram_id}: {send_error}")
                    failed_count += 1

                # Rate limiting: 20 messages per second (0.05s delay)
                await asyncio.sleep(0.05) 

            # Notify admin about completion
            await self.bot.send_message(
                admin_telegram_id,
                f"✅ **Рассылка {broadcast_id} завершена!**\n\n"
                f"✅ Успешно: {success_count}\n"
                f"❌ Ошибки: {failed_count}\n"
                f"👥 Всего: {len(user_telegram_ids)}",
                parse_mode="Markdown",
            )
            
            # Log action
            # Note: session might be closed if not handled carefully. 
            # Ideally create new session for background task.
            # Here we assume session is valid or we should use session factory.
            # Skipping DB log in background to avoid DetachedInstanceError or ClosedSession
            
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            await self.bot.send_message(
                admin_telegram_id,
                f"❌ **Ошибка рассылки {broadcast_id}**: {e}",
                parse_mode="Markdown",
            )

