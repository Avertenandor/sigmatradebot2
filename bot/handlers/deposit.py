"""
Deposit handler.

Handles deposit creation flow.
"""

import re
from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from app.models.user import User
from app.services.deposit_service import DepositService
from bot.keyboards.reply import deposit_keyboard, main_menu_reply_keyboard
from bot.states.deposit import DepositStates
from bot.utils.menu_buttons import is_menu_button

router = Router()


def extract_level_from_button(text: str) -> int:
    """
    Extract deposit level from button text.

    Args:
        text: Button text like "💰 Пополнить Level 1 (10 USDT)"

    Returns:
        Level number (1-5)
    """
    # Extract level number from text
    if (
        "Level 1" in text
        or "Level 2" in text
        or "Level 3" in text
        or "Level 4" in text
        or "Level 5" in text
    ):
        for i in range(1, 6):
            if f"Level {i}" in text:
                return i
    return 1  # Default to level 1 if not found


# Regex pattern for deposit level buttons with dynamic amounts
# Matches: "💰 Пополнить Level N (X USDT)" or "✅ Level N (X USDT) - Активен"
# or "🔒 Level N (X USDT) - ..." for blocked levels
@router.message(
    F.text.regexp(r"^(💰 Пополнить Level [1-5] \([\d\.,]+ USDT\)|✅ Level [1-5] \([\d\.,]+ USDT\) - Активен|🔒 Level [1-5] \([\d\.,]+ USDT\) - .+)$")
)
async def select_deposit_level(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle deposit level selection with validation.
    
    Uses session_factory for short transaction during validation.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    # Extract level from button text
    level = extract_level_from_button(message.text or "")
    
    # R3-3: Check if level is already active (button text contains "Активен")
    is_active_level = "Активен" in (message.text or "")
    
    # Validate purchase eligibility with SHORT transaction
    from app.services.deposit_validation_service import (
        DepositValidationService,
    )

    session_factory = data.get("session_factory")
    
    if not session_factory:
        # Fallback to old session
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка. Отправьте /start или обратитесь в поддержку.")
            return
        validation_service = DepositValidationService(session)
        can_purchase, error_msg = await validation_service.can_purchase_level(
            user.id, level
        )
        # Get level statuses for active check
        levels_status = await validation_service.get_available_levels(user.id)
    else:
        # NEW pattern: short read transaction
        async with session_factory() as session:
            async with session.begin():
                validation_service = DepositValidationService(session)
                can_purchase, error_msg = await validation_service.can_purchase_level(
                    user.id, level
                )
                # Get level statuses for active check
                levels_status = await validation_service.get_available_levels(user.id)
        # Transaction closed here

    # R3-3: Handle active level - prohibit duplicate purchase
    if is_active_level or (levels_status and levels_status.get(level, {}).get("status") == "active"):
        await message.answer(
            f"ℹ️ **Уровень {level} уже активен**\n\n"
            f"У вас уже есть активный депозит уровня {level}.\n"
            f"Повторная покупка того же уровня не разрешена.\n\n"
            f"Выберите другой уровень депозита или проверьте свои активные депозиты в разделе '📦 Мои депозиты'.",
            parse_mode="Markdown",
            reply_markup=deposit_keyboard(levels_status=levels_status),
        )
        return

    if not can_purchase:
        # R3-4: Improved error messages with specific recommendations
        error_text = "❌ **Нельзя купить этот уровень депозита**\n\n"
        
        if error_msg:
            error_text += f"{error_msg}\n\n"
            
            # Add specific recommendations based on error type
            if "необходимо сначала купить" in error_msg:
                # Extract previous level from error message
                prev_level = level - 1
                error_text += (
                    f"💡 **Рекомендация:**\n"
                    f"Сначала купите уровень {prev_level}, чтобы разблокировать уровень {level}.\n"
                    f"Порядок покупки обязателен: 1 → 2 → 3 → 4 → 5"
                )
            elif "необходимо минимум" in error_msg:
                # Extract required partners count
                from app.services.deposit_validation_service import PARTNER_REQUIREMENTS
                required = PARTNER_REQUIREMENTS.get(level, 1)
                error_text += (
                    f"💡 **Рекомендация:**\n"
                    f"Пригласите минимум {required} реферала, который создаст активный депозит уровня 1.\n"
                    f"Используйте раздел '👥 Рефералы' для приглашения партнёров."
                )
            else:
                error_text += "Попробуйте выбрать другой уровень депозита."
        else:
            error_text += "Попробуйте выбрать другой уровень депозита."
        
        await message.answer(
            error_text,
            parse_mode="Markdown",
            reply_markup=deposit_keyboard(levels_status=levels_status),
        )
        return

    # Get expected amount for this level
    from app.services.deposit_validation_service import DEPOSIT_LEVELS

    expected_amount = DEPOSIT_LEVELS[level]

    # Save level to state
    await state.update_data(level=level, expected_amount=str(expected_amount))

    # Ask for amount
    text = (
        f"📦 *Депозит уровня {level}*\n\n"
        f"💰 Сумма депозита: *{expected_amount} USDT*\n\n"
    )

    if level == 1:
        text += (
            "⚠️ Для уровня 1 действует ROI cap 500%\n"
            "(максимум можно заработать 5x от депозита)\n\n"
        )

    # Get system wallet address
    from app.config.settings import settings
    system_wallet = settings.system_wallet_address
    
    text += (
        f"📝 *Следующий шаг:*\n"
        f"Отправьте *ровно {expected_amount} USDT* на адрес:\n\n"
        f"`{system_wallet}`\n\n"
        f"⚠️ **ВАЖНО:**\n"
        f"• Сеть: **BSC (BEP-20)**\n"
        f"• Используйте личный кошелек (MetaMask, Trust Wallet, SafePal, Ledger)\n"
        f"• 🚫 Не используйте внутренние переводы бирж (Internal Transfer)\n"
        f"• 💡 Комиссия сети уже включена в сумму депозита\n\n"
        "После отправки введите hash транзакции:"
    )

    await message.answer(text, parse_mode="Markdown")
    await state.set_state(DepositStates.waiting_for_tx_hash)


# NOTE: process_deposit_amount removed - now we go directly to tx_hash
# after selecting level, as amount is fixed per level (10/50/100/150/300 USDT)


@router.message(DepositStates.waiting_for_tx_hash)
async def process_tx_hash(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Process transaction hash for deposit.
    
    Uses session_factory for short transaction during deposit creation.

    Args:
        message: Telegram message
        state: FSM state
        data: Additional data including session_factory and user
    """
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Check if message is a menu button - if so, clear state and ignore
    if is_menu_button(message.text or ""):
        await state.clear()
        return  # Let menu handlers process this

    tx_hash = (message.text or "").strip()

    # Basic validation
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        await message.answer(
            "❌ Неверный формат hash!\n\n"
            "Transaction hash должен начинаться с '0x' "
            "и содержать 66 символов.\n"
            "Попробуйте еще раз:"
        )
        return

    # Get level and expected amount from state
    state_data = await state.get_data()
    level = state_data.get("level", 1)
    expected_amount_str = state_data.get("expected_amount")

    if expected_amount_str:
        expected_amount = Decimal(expected_amount_str)
    else:
        from app.services.deposit_validation_service import DEPOSIT_LEVELS

        expected_amount = DEPOSIT_LEVELS.get(level, Decimal("10"))

    session_factory = data.get("session_factory")

    # Validate and create deposit with SHORT transaction
    if not session_factory:
        # Fallback to old session
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка.")
            await state.clear()
            return

        from app.services.deposit_validation_service import (
            DepositValidationService,
        )

        validation_service = DepositValidationService(session)
        can_purchase, error_msg = await validation_service.can_purchase_level(
            user.id, level
        )

        if not can_purchase:
            await message.answer(
                f"❌ {error_msg}\n\nПопробуйте выбрать другой уровень."
            )
            await state.clear()
            return

        deposit_service = DepositService(session)
        redis_client = data.get("redis_client")
        try:
            deposit = await deposit_service.create_deposit(
                user_id=user.id,
                level=level,
                amount=expected_amount,
                tx_hash=tx_hash,
                redis_client=redis_client,
            )
        except ValueError as exc:
            # R17-3: Show controlled business errors (including emergency stop)
            await message.answer(str(exc))
            await state.clear()
            return
    else:
        # NEW pattern: short transaction for validation and creation
        async with session_factory() as session:
            async with session.begin():
                from app.services.deposit_validation_service import (
                    DepositValidationService,
                )
                validation_service = DepositValidationService(session)
                can_purchase, error_msg = await validation_service.can_purchase_level(
                    user.id, level
                )

                if not can_purchase:
                    await message.answer(
                        f"❌ {error_msg}\n\nПопробуйте выбрать другой уровень."
                    )
                    await state.clear()
                    return

                deposit_service = DepositService(session)
                redis_client = data.get("redis_client")
                try:
                    deposit = await deposit_service.create_deposit(
                        user_id=user.id,
                        level=level,
                        amount=expected_amount,
                        tx_hash=tx_hash,
                        redis_client=redis_client,
                    )
                except ValueError as exc:
                    # R17-3: Show controlled business errors (including emergency stop)
                    await message.answer(str(exc))
                    await state.clear()
                    return
        # Transaction closed here

    logger.info(
        "Deposit created with tx hash",
        extra={
            "deposit_id": deposit.id,
            "user_id": user.id,
            "level": level,
            "amount": str(expected_amount),
            "tx_hash": tx_hash,
        },
    )

    # Get system wallet address
    from app.config.settings import settings

    system_wallet = settings.system_wallet_address

    # Show deposit info with payment address
    text = (
        f"✅ **Депозит создан!**\n\n"
        f"📦 Уровень: {level}\n"
        f"💰 Сумма: {expected_amount} USDT\n"
        f"🆔 ID депозита: {deposit.id}\n"
        f"🔗 Hash транзакции: `{tx_hash}`\n\n"
    )

    if level == 1:
        roi_cap = expected_amount * Decimal("5.0")
        text += f"💰 ROI Cap: {roi_cap} USDT (максимум можно заработать)\n\n"

    text += (
        f"📝 **Следующий шаг:**\n"
        f"Отправьте {expected_amount} USDT на адрес:\n"
        f"`{system_wallet}`\n\n"
        f"🌐 **Сеть:** BSC (BEP-20)\n"
        f"⚠️ **ВАЖНО:**\n"
        f"• Используйте личный кошелек (MetaMask, Trust Wallet, SafePal, Ledger)\n"
        f"• 🚫 Не используйте внутренние переводы бирж\n\n"
        f"⏱ После отправки депозит будет автоматически активирован "
        f"после подтверждения транзакции (обычно 1-3 минуты).\n\n"
        f"📊 **Проверить транзакцию:**\n"
        f"https://bscscan.com/tx/{tx_hash}"
    )

    is_admin = data.get("is_admin", False)
    
    # Get blacklist entry with proper session handling
    from app.repositories.blacklist_repository import BlacklistRepository
    blacklist_entry = None
    if user and session_factory:
        async with session_factory() as fresh_session:
            blacklist_repo = BlacklistRepository(fresh_session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(
                user.telegram_id
            )
    elif user and data.get("session"):
        blacklist_repo = BlacklistRepository(data.get("session"))
        blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu_reply_keyboard(
            user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
        ),
    )
    await state.clear()
