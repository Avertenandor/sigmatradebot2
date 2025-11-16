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


# Support menu handler moved to bot/handlers/support.py
# Removed to avoid handler conflicts

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
    """Show detailed user profile."""
    from app.services.deposit_service import DepositService
    from bot.utils.formatters import format_usdt
    
    user_service = UserService(session)
    deposit_service = DepositService(session)
    
    # Get user stats
    stats = await user_service.get_user_stats(user.id)
    
    # Get user balance
    balance = await user_service.get_user_balance(user.id)
    
    # Get ROI progress for level 1
    roi_progress = await deposit_service.get_level1_roi_progress(user.id)
    
    # Get referral link
    from app.config.settings import settings
    bot_username = settings.telegram_bot_username
    referral_link = user_service.generate_referral_link(user.id, bot_username)
    
    # Build ROI section
    roi_section = ""
    if roi_progress.get("has_active_deposit") and not roi_progress.get("is_completed"):
        progress_percent = roi_progress.get("roi_percent", 0)
        filled = round((progress_percent / 100) * 10)
        empty = 10 - filled
        progress_bar = "█" * filled + "░" * empty
        
        roi_section = (
            f"\n*🎯 ROI Прогресс (Уровень 1):*\n"
            f"💵 Депозит: {format_usdt(roi_progress.get('deposit_amount', 0))} USDT\n"
            f"📊 Прогресс: {progress_bar} {progress_percent:.1f}%\n"
            f"✅ Получено: {format_usdt(roi_progress.get('roi_paid', 0))} USDT\n"
            f"⏳ Осталось: {format_usdt(roi_progress.get('roi_remaining', 0))} USDT\n"
            f"🎯 Цель: {format_usdt(roi_progress.get('roi_cap', 0))} USDT (500%)\n\n"
        )
    elif roi_progress.get("has_active_deposit") and roi_progress.get("is_completed"):
        roi_section = (
            f"\n*🎯 ROI Завершён (Уровень 1):*\n"
            f"✅ Достигнут максимум 500%!\n"
            f"💰 Получено: {format_usdt(roi_progress.get('roi_paid', 0))} USDT\n"
            f"📌 Создайте новый депозит чтобы продолжить\n\n"
        )
    
    # Format wallet address
    wallet_display = user.wallet_address
    if len(user.wallet_address) > 20:
        wallet_display = f"{user.wallet_address[:10]}...{user.wallet_address[-8:]}"
    
    text = (
        f"👤 *Ваш профиль*\n\n"
        f"*Основная информация:*\n"
        f"🆔 ID: `{user.id}`\n"
        f"👤 Username: @{user.username or 'не указан'}\n"
        f"💳 Кошелек: `{wallet_display}`\n\n"
        f"*Статус:*\n"
        f"{'✅' if user.is_verified else '❌'} Верификация: {'Пройдена' if user.is_verified else 'Не пройдена'}\n"
        f"{'🚫 Аккаунт заблокирован' if user.is_banned else '✅ Аккаунт активен'}\n\n"
        f"*Баланс:*\n"
        f"💰 Доступно для вывода: *{format_usdt(balance.get('available_balance', 0))} USDT*\n"
        f"💸 Всего заработано: {format_usdt(balance.get('total_earned', 0))} USDT\n"
        f"⏳ В ожидании выплаты: {format_usdt(balance.get('pending_earnings', 0))} USDT\n"
    )
    
    if balance.get('pending_withdrawals', 0) > 0:
        text += f"🔒 Заблокировано в выводах: {format_usdt(balance.get('pending_withdrawals', 0))} USDT\n"
    
    text += f"✅ Уже выплачено: {format_usdt(balance.get('total_paid', 0))} USDT\n"
    text += roi_section
    text += (
        f"*Депозиты и рефералы:*\n"
        f"💰 Всего депозитов: {format_usdt(stats.get('total_deposits', 0))} USDT\n"
        f"👥 Рефералов: {stats.get('referral_count', 0)}\n"
        f"📊 Активных уровней: {len(stats.get('activated_levels', []))}/5\n\n"
    )
    
    if user.phone or user.email:
        text += "*Контакты:*\n"
        if user.phone:
            text += f"📞 {user.phone}\n"
        if user.email:
            text += f"📧 {user.email}\n"
        text += "\n"
    
    text += (
        f"*Реферальная ссылка:*\n"
        f"`{referral_link}`\n\n"
        f"📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}"
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

