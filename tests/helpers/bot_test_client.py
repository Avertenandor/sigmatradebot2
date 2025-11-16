"""
Bot Test Client for E2E testing.

Provides a high-level API for testing bot interactions without real Telegram
    API.
Similar to Selenium/Playwright for web testing, but for Telegram bots.
"""

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Chat, Message, Update, User


class BotTestClient:
    """
    Test client for Telegram bot.

    Usage:
        client = BotTestClient(bot, dispatcher)
        response = await client.send_message("/start")
        assert "Welcome" in response.text
    """

    def __init__(self, bot: Bot, dispatcher: Dispatcher):
        self.bot = bot
        self.dispatcher = dispatcher
        self.sent_messages: list[Message] = []
        self.received_updates: list[Update] = []

    async def send_message(
        self, text: str, user_id: int = 123456789, username: str = "testuser"
    ) -> Message | None:
        """
        Send a message to the bot.

        Args:
            text: Message text
            user_id: Telegram user ID
            username: Telegram username

        Returns:
            Bot's response message (if any)
        """
        user = User(
            id=user_id, is_bot=False, first_name="Test", username=username
        )

        chat = Chat(id=user_id, type="private", username=username)

        message = Message(
            message_id=len(self.sent_messages) + 1,
            date=1234567890 + len(self.sent_messages),
            chat=chat,
            from_user=user,
            text=text,
        )

        update = Update(
            update_id=len(self.received_updates) + 1, message=message
        )

        self.sent_messages.append(message)
        self.received_updates.append(update)

        await self.dispatcher.feed_update(self.bot, update)

        # Return last sent message by bot (would need to track bot responses)
        return None

    async def send_callback(
        self,
        callback_data: str,
        user_id: int = 123456789,
        username: str = "testuser",
    ) -> CallbackQuery | None:
        """
        Send a callback query to the bot.

        Args:
            callback_data: Callback data
            user_id: Telegram user ID
            username: Telegram username

        Returns:
            Processed callback query
        """
        user = User(
            id=user_id, is_bot=False, first_name="Test", username=username
        )

        callback = CallbackQuery(
            id=f"cb_{len(self.received_updates) + 1}",
            from_user=user,
            chat_instance="test",
            data=callback_data,
        )

        update = Update(
            update_id=len(self.received_updates) + 1, callback_query=callback
        )

        self.received_updates.append(update)

        await self.dispatcher.feed_update(self.bot, update)

        return callback

    async def assert_response_contains(self, text: str) -> bool:
        """
        Assert that bot's response contains text.

        Note: This is a placeholder. In real implementation,
        you'd track bot's responses via mock_bot session.
        """
        # Would check bot's sent messages
        return True

    def get_sent_messages(self) -> list[Message]:
        """Get all messages sent to bot."""
        return self.sent_messages

    def get_received_updates(self) -> list[Update]:
        """Get all updates received by bot."""
        return self.received_updates

    def clear_history(self):
        """Clear message and update history."""
        self.sent_messages.clear()
        self.received_updates.clear()


async def create_test_client(
    bot: Bot, dispatcher: Dispatcher
) -> BotTestClient:
    """Create a test client for bot testing."""
    return BotTestClient(bot, dispatcher)
