"""
Menu state clear middleware.

Clears FSM state when menu buttons are pressed to prevent FSM handlers
from intercepting menu button messages.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger

from bot.utils.menu_buttons import is_menu_button
from bot.utils.admin_utils import clear_state_preserve_admin_token


class MenuStateClearMiddleware(BaseMiddleware):
    """
    Middleware that clears FSM state when menu buttons are pressed.

    This ensures menu buttons are processed by menu handlers, not FSM handlers.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Process event and clear state if menu button is pressed.

        Args:
            handler: Next handler in chain
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        # Only process Message events with text
        if isinstance(event, Message) and event.text:
            # Check if message is a menu button
            if is_menu_button(event.text):
                # Get FSM context from data
                # (provided by aiogram's FSM middleware)
                # In aiogram 3.x, state is available in data["state"]
                state = data.get("state")
                if state:
                    try:
                        # Clear state to prevent FSM handlers from intercepting
                        current_state = await state.get_state()
                        if current_state is not None:
                            logger.debug(
                                f"Clearing FSM state {current_state} for "
                                f"menu button: {event.text}"
                            )
                            # Use helper to preserve admin token
                            await clear_state_preserve_admin_token(state)
                            logger.debug(
                                f"FSM state cleared for menu button: "
                                f"{event.text}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to clear FSM state: {e}")

        # Continue to next handler
        return await handler(event, data)
