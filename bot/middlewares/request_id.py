"""
Request ID middleware (PART5 critical).

Assigns unique request ID to every update for tracing.
MUST be the first middleware in the chain.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from loguru import logger


class RequestIDMiddleware(BaseMiddleware):
    """
    Request ID middleware.

    Generates unique request_id for each update for tracing across logs.
    PART5 requirement: Must be first middleware for complete tracing.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Process update with request ID.

        Args:
            handler: Next handler
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Add to data for downstream handlers
        data["request_id"] = request_id
        
        # Store Update object for logger_middleware
        if isinstance(event, Update):
            data["event_update"] = event

        # Add to logger context
        with logger.contextualize(request_id=request_id):
            # Log incoming update
            if isinstance(event, Update):
                update_type = "unknown"
                if event.message:
                    update_type = "message"
                elif event.callback_query:
                    update_type = "callback"
                elif event.inline_query:
                    update_type = "inline_query"

                logger.info(
                    f"Incoming {update_type}",
                    extra={
                        "update_id": event.update_id,
                        "user_id": (
                            event.message.from_user.id
                            if event.message
                            else (
                                event.callback_query.from_user.id
                                if event.callback_query
                                else None
                            )
                        ),
                    },
                )

            # Call next handler
            return await handler(event, data)
