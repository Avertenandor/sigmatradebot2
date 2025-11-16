"""
Menu handler.

Handles main menu navigation - ТОЛЬКО REPLY KEYBOARDS!
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.blacklist_repository import BlacklistRepository
from app.services.transaction_service import TransactionService
from app.services.user_service import UserService
from bot.keyboards.reply import (
    deposit_keyboard,
    main_menu_reply_keyboard,
    referral_keyboard,
    settings_keyboard,
    support_keyboard,
    withdrawal_keyboard,
)
from bot.states.update_contacts import UpdateContactsStates
from bot.utils.menu_buttons import is_menu_button

router = Router()


async def show_main_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """
    Show main menu.
    
    Args:
        message: Message object
        session: Database session
        user: Current user
        state: FSM state
    """
    # Clear any active FSM state
    await state.clear()
    
    # Get blacklist status
    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = await blacklist_repo.get_active_blacklist(user.telegram_id)
    
    # Check if user is admin
    from app.config.settings import settings
    is_admin = user.telegram_id in settings.get_admin_ids()
    
    text = (
        f"📊 *Главное меню*\n\n"
        f"Добро пожаловать, {user.username or 'пользователь'}!\n\n"
        f"Выберите действие из меню ниже:"
    )
    
    await message.answer(
        text,
        reply_markup=main_menu_reply_keyboard(
            user=user,
            blacklist_entry=blacklist_entry,
            is_admin=is_admin
        ),
        parse_mode="Markdown"
    )


@router.message(F.text == "📊 Главное меню")
async def handle_main_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Handle main menu button."""
    await show_main_menu(message, session, user, state)


@router.message(F.text == "📊 Баланс")
async def show_balance(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Show user balance."""
    await state.clear()
    
    user_service = UserService(session)
    balance = await user_service.get_user_balance(user.id)

    if not balance:
        await message.answer("❌ Ошибка получения баланса")
        return

    text = (
        f"💰 *Ваш баланс:*\n\n"
        f"Общий: `{balance['total_balance']:.2f} USDT`\n"
        f"Доступно: `{balance['available_balance']:.2f} USDT`\n"
        f"В ожидании: `{balance['pending_earnings']:.2f} USDT`\n\n"
        f"📊 *Статистика:*\n"
        f"Депозиты: `{balance['total_deposits']:.2f} USDT`\n"
        f"Выводы: `{balance['total_withdrawals']:.2f} USDT`\n"
        f"Заработано: `{balance['total_earnings']:.2f} USDT`"
    )

    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "💰 Депозит")
async def show_deposit_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Show deposit menu."""
    await state.clear()

    from app.config.settings import settings
    
    text = (
        f"💰 *Выберите уровень депозита:*\n\n"
        f"Level 1: `{settings.deposit_level_1:.0f} USDT`\n"
        f"Level 2: `{settings.deposit_level_2:.0f} USDT`\n"
        f"Level 3: `{settings.deposit_level_3:.0f} USDT`\n"
        f"Level 4: `{settings.deposit_level_4:.0f} USDT`\n"
        f"Level 5: `{settings.deposit_level_5:.0f} USDT`"
    )

    await message.answer(
        text,
        reply_markup=deposit_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "💸 Вывод")
async def show_withdrawal_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Show withdrawal menu."""
    await state.clear()

    user_service = UserService(session)
    balance = await user_service.get_user_balance(user.id)

    text = (
        f"💸 *Вывод средств*\n\n"
        f"Доступно для вывода: `{balance['available_balance']:.2f} USDT`\n\n"
        f"Выберите действие:"
    )

    await message.answer(
        text,
        reply_markup=withdrawal_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "👥 Рефералы")
async def show_referral_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Show referral menu."""
    await state.clear()

    from app.config.settings import settings
    bot_username = settings.telegram_bot_username
    referral_link = f"https://t.me/{bot_username}?start={user.telegram_id}"

    text = (
        f"👥 *Реферальная программа*\n\n"
        f"Ваша реферальная ссылка:\n"
        f"`{referral_link}`\n\n"
        f"Приглашайте друзей и получайте вознаграждение!"
    )

    await message.answer(
        text,
        reply_markup=referral_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "💬 Поддержка")
async def show_support_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Show support menu."""
    await state.clear()

    text = (
        f"💬 *Служба поддержки*\n\n"
        f"Выберите действие:"
    )

    await message.answer(
        text,
        reply_markup=support_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "⚙️ Настройки")
async def show_settings_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Show settings menu."""
    await state.clear()

    text = (
        f"⚙️ *Настройки*\n\n"
        f"Выберите раздел:"
    )

    await message.answer(
        text,
        reply_markup=settings_keyboard(),
        parse_mode="Markdown"
    )


# Handlers для submenu кнопок

@router.message(F.text == "👥 Мои рефералы")
async def show_my_referrals(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user's referrals list."""
    user_service = UserService(session)
    
    # TODO: Implement referral list logic
    text = "👥 *Мои рефералы*\n\nФункция в разработке"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "💰 Мой заработок")
async def show_my_earnings(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user's referral earnings."""
    # TODO: Implement earnings logic
    text = "💰 *Мой заработок*\n\nФункция в разработке"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "📊 Статистика рефералов")
async def show_referral_stats(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show referral statistics."""
    # TODO: Implement stats logic
    text = "📊 *Статистика рефералов*\n\nФункция в разработке"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "👤 Мой профиль")
async def show_my_profile(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user profile."""
    text = (
        f"👤 *Мой профиль*\n\n"
        f"Username: @{user.username or 'не указан'}\n"
        f"Telegram ID: `{user.telegram_id}`\n"
        f"Кошелек: `{user.wallet_address[:10]}...{user.wallet_address[-8:]}`\n"
        f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "💳 Мой кошелек")
async def show_my_wallet(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Show user wallet."""
    text = (
        f"💳 *Мой кошелек*\n\n"
        f"Адрес: `{user.wallet_address}`\n\n"
        f"⚠️ Сохраните приватный ключ в безопасном месте!"
    )
    
    await message.answer(text, parse_mode="Markdown")

