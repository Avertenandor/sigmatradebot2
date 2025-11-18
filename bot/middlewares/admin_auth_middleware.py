"""
Admin authentication middleware.

Checks admin session and requires master key authentication for admin actions.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.admin_session import AdminSession
from app.services.admin_service import AdminService
from bot.states.admin_states import AdminStates


class AdminAuthMiddleware(BaseMiddleware):
    """
    Admin authentication middleware.

    Checks for active admin session and requires master key if missing.
    Updates session activity on each admin action.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Check admin session and authenticate if needed.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        # Get session from data (provided by DatabaseMiddleware)
        session: AsyncSession = data.get("session")
        if not session:
            logger.error(
                "No session in data - DatabaseMiddleware missing?"
            )
            return await handler(event, data)

        # Get FSM context
        state: FSMContext = data.get("state")
        if not state:
            logger.error("No state in data - FSMContext missing?")
            return await handler(event, data)

        # Get telegram user
        telegram_user = data.get("event_from_user")
        if not telegram_user:
            if isinstance(event, Message):
                telegram_user = event.from_user
            elif isinstance(event, CallbackQuery):
                telegram_user = event.from_user

        if not telegram_user:
            return await handler(event, data)

        # Check if user is admin
        is_admin = data.get("is_admin", False)
        if not is_admin:
            # Not an admin, skip middleware
            return await handler(event, data)

        # Get admin from database
        admin_service = AdminService(session)
        admin = await admin_service.get_admin_by_telegram_id(
            telegram_user.id
        )

        if not admin:
            logger.warning(
                f"User {telegram_user.id} marked as admin but not found "
                f"in Admin table"
            )
            return await handler(event, data)

        # Get current FSM state
        current_state = await state.get_state()

        # Check if we're already in master key input state
        if current_state == AdminStates.awaiting_master_key_input:
            # Let handler process master key input
            return await handler(event, data)

        # Get session token from FSM state
        state_data = await state.get_data()
        session_token = state_data.get("admin_session_token")

        # If no session token, require master key
        if not session_token:
            # Check if this is a master key input (handler will process it)
            # For now, require master key
            await state.set_state(AdminStates.awaiting_master_key_input)
            if isinstance(event, Message):
                await event.answer(
                    "🔐 **Требуется аутентификация**\n\n"
                    "Для доступа к админ-панели введите мастер-ключ:",
                    parse_mode="Markdown",
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "🔐 Требуется аутентификация. Введите мастер-ключ."
                )
            return

        # Validate session
        admin_obj, session_obj, error = await admin_service.validate_session(
            session_token
        )

        if error or not admin_obj or not session_obj:
            # Session invalid, require master key
            await state.set_state(AdminStates.awaiting_master_key_input)
            await state.update_data(admin_session_token=None)
            if isinstance(event, Message):
                await event.answer(
                    f"❌ {error or 'Сессия недействительна'}\n\n"
                    "Введите мастер-ключ для повторной аутентификации:",
                    parse_mode="Markdown",
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"❌ {error or 'Сессия недействительна'}"
                )
            return

        # Session is valid, add to data
        data["admin"] = admin_obj
        data["admin_session"] = session_obj
        data["admin_session_token"] = session_token
        data["is_super_admin"] = admin_obj.is_super_admin
        data["is_extended_admin"] = admin_obj.is_extended_admin

        # Note: validate_session already updates last_activity
        # So we don't need to update it again here

        # Call next handler
        return await handler(event, data)

