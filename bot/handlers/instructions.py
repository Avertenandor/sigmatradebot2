"""
Instructions handler - ТОЛЬКО REPLY KEYBOARDS!

Provides deposit instructions and BSCScan links.
R1-5: Shows basic platform description for guests.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from bot.keyboards.reply import (
    deposit_keyboard,
    main_menu_reply_keyboard,
)

router = Router()


@router.message(F.text == "📖 Инструкции")
async def show_instructions(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show instructions.

    R1-5: For guests, shows basic platform description.
    For registered users, shows deposit instructions.

    Args:
        message: Telegram message
        session: Database session
        state: FSM state
        data: Additional data from middlewares
    """
    from app.config.settings import settings
    from app.repositories.blacklist_repository import BlacklistRepository

    user: User | None = data.get("user")
    is_admin = data.get("is_admin", False)

    # R1-6: Проверка FSM состояния - если пользователь в процессе регистрации,
    # сбросить состояние и показать главное меню
    from bot.states.registration import RegistrationStates
    from bot.utils.menu_buttons import is_menu_button
    
    current_state = await state.get_state()
    if current_state and current_state in [
        RegistrationStates.waiting_for_wallet,
        RegistrationStates.waiting_for_financial_password,
        RegistrationStates.waiting_for_password_confirmation,
        RegistrationStates.waiting_for_contacts_choice,
        RegistrationStates.waiting_for_phone,
        RegistrationStates.waiting_for_email,
    ]:
        # R1-6: Пользователь в процессе регистрации, нажал "📖 Инструкции"
        # Сбрасываем FSM состояние и показываем главное меню
        await state.clear()
        if not user:
            # Гость - показываем главное меню для гостя
            await message.answer(
                "📊 Главное меню",
                reply_markup=main_menu_reply_keyboard(
                    user=None, blacklist_entry=None, is_admin=is_admin
                ),
            )
        else:
            # Зарегистрированный пользователь - показываем главное меню
            from app.repositories.blacklist_repository import BlacklistRepository
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(user.telegram_id)
            await message.answer(
                "📊 Главное меню",
                reply_markup=main_menu_reply_keyboard(
                    user=user, blacklist_entry=blacklist_entry, is_admin=is_admin
                ),
            )
        return

    # R1-5: Инструкции до регистрации - базовое описание для гостей
    if not user:
        # Clear any active FSM state (R1-6: инструкции во время регистрации)
        await state.clear()

        instructions_text = (
            "📖 *О платформе SigmaTrade*\n\n"
            "SigmaTrade — это платформа для инвестиций в USDT на сети "
            "Binance Smart Chain (BEP-20).\n\n"
            "**Основные возможности:**\n"
            "• Инвестиции в USDT с автоматическими начислениями\n"
            "• Партнерская программа с вознаграждениями\n"
            "• Прозрачная система депозитов и выводов\n"
            "• Безопасная работа на блокчейне BSC\n\n"
            "**Важно:**\n"
            "• Работа ведется только с сетью **BSC (BEP-20)**\n"
            "• Базовая валюта депозитов — **USDT BEP-20**\n\n"
            "🌐 **Официальный сайт:**\n"
            "[sigmatrade.org](https://sigmatrade.org/index.html#exchange)\n\n"
            "📝 **Для начала работы необходимо пройти регистрацию.**\n"
            "Используйте кнопку '📝 Регистрация' или команду /start."
        )

        await message.answer(
            instructions_text,
            parse_mode="Markdown",
            reply_markup=main_menu_reply_keyboard(
                user=None, blacklist_entry=None, is_admin=is_admin
            ),
        )
        return

    # For registered users: show deposit instructions
    instructions_text = (
        "📖 *Инструкция по пополнению депозита*\n\n"
        "*1️⃣ Откройте ваш BSC кошелек* (Trust Wallet, MetaMask и т.д.)\n\n"
        "*2️⃣ Отправьте USDT (BEP-20)* на следующий адрес:\n"
        f"`{settings.system_wallet_address}`\n\n"
        "*3️⃣ Сумма депозита:*\n"
        f"   • Уровень 1: {settings.deposit_level_1} USDT\n"
        f"   • Уровень 2: {settings.deposit_level_2} USDT\n"
        f"   • Уровень 3: {settings.deposit_level_3} USDT\n"
        f"   • Уровень 4: {settings.deposit_level_4} USDT\n"
        f"   • Уровень 5: {settings.deposit_level_5} USDT\n\n"
        "*4️⃣ Дождитесь подтверждения* (обычно 1-3 минуты)\n\n"
        "*5️⃣ Депозит активируется автоматически* после 12 подтверждений"
            "блоков\n\n"
        "⚠️ *Важно:*\n"
        "• Отправляйте только USDT (BEP-20) на BSC сети!\n"
        "• Используйте личный кошелек (MetaMask, Trust Wallet)\n"
        "• 🚫 Не используйте вывод с бирж (Internal Transfer)\n"
        "• Убедитесь, что сумма точно совпадает с уровнем депозита\n"
        "• Сохраните hash транзакции для отслеживания\n\n"
        "*📋 Правила работы системы депозитов:*\n\n"
        "*Порядок покупки:*\n"
        "• Депозиты можно покупать только по возрастающей (1→2→3→4→5)\n"
        "• Нельзя пропустить уровень (например, купить уровень 3 без"
            "уровня 2)\n"
        "• Уровень 1 (50 USDT) можно купить без партнеров\n"
        "• Для уровней 2+ требуется наличие активных партнеров уровня 1\n\n"
        "*Партнерская программа:*\n"
        "• Приглашайте друзей по вашей реферальной ссылке\n"
        "• Новый пользователь становится вашим партнером уровня L1\n"
        "• Вы получаете вознаграждения за активность партнеров\n"
        "• Партнеры влияют на возможность покупки более высоких уровней\n\n"
        "*ROI и ограничения:*\n"
        "• Для уровня 1 действует ROI cap 500% (максимум 5x от депозита)\n"
        "• Начисления происходят автоматически\n"
        "• Вывод средств доступен только после верификации\n\n"
        "*🌐 Подробная информация:*\n"
        "Больше информации о платформе, условиях и правилах можно найти на "
        "[официальном сайте](https://sigmatrade.org/index.html#exchange).\n\n"
        f"*🔍 Проверить транзакцию:*\n"
        f"BSCScan: https://bscscan.com/address/{settings.system_wallet_address}"
    )

    # Get actual level statuses for deposit keyboard
    from app.services.deposit_validation_service import DepositValidationService
    
    validation_service = DepositValidationService(session)
    levels_status = await validation_service.get_available_levels(user.id)
    
    await message.answer(
        instructions_text,
        parse_mode="Markdown",
        reply_markup=deposit_keyboard(levels_status=levels_status),
    )
