"""
Verification handler.

Handles user verification with financial password generation.
"""

import secrets
import string
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.user_service import UserService
from bot.keyboards.reply import main_menu_reply_keyboard

router = Router(name="verification")


def generate_financial_password(length: int = 8) -> str:
    """
    Generate random financial password.

    Args:
        length: Password length (default 8)

    Returns:
        Random password string
    """
    # Use digits and uppercase letters for better readability
    alphabet = string.digits + string.ascii_uppercase
    # Exclude confusing characters: 0, O, I, 1
    alphabet = (
        alphabet.replace("0", "")
        .replace("O", "")
        .replace("I", "")
        .replace("1", "")
    )
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password


@router.message(F.text == "✅ Пройти верификацию")
async def start_verification(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start verification process - generate financial password.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
        **data: Handler data (includes user from AuthMiddleware)
    """
    # Get user from middleware data
    user: User | None = data.get("user")
    if not user:
        logger.error("start_verification: No user in data")
        await message.answer("❌ Ошибка: пользователь не найден. Попробуйте /start")
        return

    # Clear any active FSM state
    await state.clear()

    # Check if already verified
    if user.is_verified:
        message_text = (
            "✅ Вы уже прошли верификацию!\n\n"
            "Ваш финансовый пароль уже установлен. "
            "Если вы забыли пароль, обратитесь в поддержку.\n\n"
            "Теперь вам доступен вывод через меню '💸 Вывод'."
        )

        is_admin = data.get("is_admin", False)
        from app.repositories.blacklist_repository import BlacklistRepository
        blacklist_repo = BlacklistRepository(session)
        blacklist_entry = None
        if user:
            blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
        await message.answer(
            message_text,
            reply_markup=main_menu_reply_keyboard(
                user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
            ),
        )
        return

    # Check verification rate limit
    telegram_id = message.from_user.id if message.from_user else None
    if telegram_id:
        from bot.utils.operation_rate_limit import OperationRateLimiter

        redis_client = data.get("redis_client")
        rate_limiter = OperationRateLimiter(redis_client=redis_client)
        allowed, error_msg = await rate_limiter.check_verification_limit(
            telegram_id
        )
        if not allowed:
            await message.answer(error_msg or "Слишком много попыток верификации")
            return

    # Generate financial password
    financial_password = generate_financial_password(8)

    # Hash and save password
    user_service = UserService(session)

    # Import bcrypt hashing
    import bcrypt

    password_hash = bcrypt.hashpw(
        financial_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    # Update user
    await user_service.update_profile(
        user.id,
        financial_password=password_hash,
        is_verified=True,
    )

    logger.info(
        "User verified with generated password",
        extra={
            "user_id": user.id,
            "telegram_id": user.telegram_id,
        },
    )

    # Show password ONCE with warning
    password_message = (
        "🔐 *Финансовый пароль сгенерирован!*\n\n"
        f"*Ваш пароль:* `{financial_password}`\n\n"
        "⚠️ *ВАЖНО:*\n"
        "• Сохраните этот пароль в безопасном месте\n"
        "• Он нужен для подтверждения финансовых операций\n"
        "• Пароль больше НЕ будет показан\n"
        "• При утере пароля обратитесь в поддержку\n\n"
        "✅ Верификация завершена!"
    )

    is_admin = data.get("is_admin", False)
    from app.repositories.blacklist_repository import BlacklistRepository
    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
    await message.answer(
        password_message,
        parse_mode="Markdown",
        reply_markup=main_menu_reply_keyboard(
            user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
        ),
    )
