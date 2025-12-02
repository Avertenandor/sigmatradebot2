"""
Account recovery handler.

R16-3: Handles recovery of lost Telegram account access.
"""

from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.account_recovery_service import AccountRecoveryService
from bot.keyboards.reply import main_menu_reply_keyboard
from bot.states.account_recovery import AccountRecoveryStates

router = Router()


@router.message(Command("recover_account"))
async def cmd_recover_account(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Start account recovery process.

    R16-3: User lost access to Telegram account but has wallet access.
    """
    telegram_id = message.from_user.id if message.from_user else None
    
    logger.info(
        f"R16-3: Account recovery initiated by telegram_id={telegram_id}"
    )
    
    await state.set_state(AccountRecoveryStates.waiting_for_wallet)

    text = (
        "🔐 **Восстановление доступа к аккаунту**\n\n"
        "Если вы потеряли доступ к своему Telegram аккаунту, "
        "но имеете доступ к кошельку, вы можете восстановить аккаунт.\n\n"
        "**Процесс восстановления:**\n"
        "1. Укажите адрес вашего кошелька\n"
        "2. Подпишите сообщение своим приватным ключом\n"
        "3. (Опционально) Укажите email или телефон для дополнительной проверки\n\n"
        "**Важно:**\n"
        "• Старый Telegram аккаунт будет заблокирован\n"
        "• Финансовый пароль будет сброшен\n"
        "• Все средства и депозиты останутся нетронутыми\n\n"
        "📝 **Шаг 1:** Отправьте адрес вашего кошелька (0x...)"
    )

    await message.answer(text, parse_mode="Markdown")


@router.message(AccountRecoveryStates.waiting_for_wallet)
async def handle_wallet_address(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle wallet address input.

    R16-3: Validate wallet address and check if account exists.
    """
    wallet_address = message.text.strip()

    # Basic validation
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        await message.answer(
            "❌ Неверный формат адреса кошелька.\n\n"
            "Адрес должен начинаться с 0x и содержать 42 символа.\n"
            "Пример: 0x1234567890123456789012345678901234567890\n\n"
            "Попробуйте еще раз:"
        )
        return

    recovery_service = AccountRecoveryService(session)

    # Check if account exists for this wallet
    recovery_info = await recovery_service.get_recovery_info(wallet_address)

    if not recovery_info:
        logger.warning(
            f"R16-3: Account recovery failed - wallet not found: {wallet_address}, "
            f"telegram_id={message.from_user.id if message.from_user else None}"
        )
        await message.answer(
            "❌ Аккаунт с таким кошельком не найден.\n\n"
            "Убедитесь, что вы указали правильный адрес кошелька, "
            "который был привязан к вашему аккаунту.\n\n"
            "Если проблема сохраняется, обратитесь в поддержку."
        )
        await state.clear()
        return
    
    logger.info(
        f"R16-3: Wallet found for recovery: {wallet_address}, "
        f"has_deposits={recovery_info.get('has_deposits')}, "
        f"has_balance={recovery_info.get('has_balance')}"
    )

    # Store wallet address in state
    await state.update_data(wallet_address=wallet_address, recovery_info=recovery_info)

    # Generate message for signing
    import secrets
    recovery_code = secrets.token_hex(16)

    await state.update_data(recovery_code=recovery_code)

    text = (
        f"✅ Кошель найден в системе.\n\n"
        f"**Информация об аккаунте:**\n"
        f"• Есть депозиты: {'Да' if recovery_info.get('has_deposits') else 'Нет'}\n"
        f"• Есть баланс: {'Да' if recovery_info.get('has_balance') else 'Нет'}\n\n"
        f"📝 **Шаг 2:** Подпишите следующее сообщение своим приватным ключом:\n\n"
        f"```\n"
        f"Account Recovery: {recovery_code}\n"
        f"Wallet: {wallet_address}\n"
        f"```\n\n"
        f"**Как подписать:**\n"
        f"1. Скопируйте сообщение выше\n"
        f"2. Используйте MetaMask, Trust Wallet, SafePal или другой кошелек\n"
        f"3. Найдите функцию 'Sign Message' или 'Подписать сообщение'\n"
        f"4. Вставьте сообщение и подпишите\n"
        f"5. Отправьте полученную подпись (signature) сюда"
    )

    await state.set_state(AccountRecoveryStates.waiting_for_signature)
    await message.answer(text, parse_mode="Markdown")


@router.message(AccountRecoveryStates.waiting_for_signature)
async def handle_signature(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle signature verification.

    R16-3: Verify wallet ownership through signature.
    """
    signature = message.text.strip()

    # Get data from state
    state_data = await state.get_data()
    wallet_address = state_data.get("wallet_address")
    recovery_code = state_data.get("recovery_code")

    if not wallet_address or not recovery_code:
        await message.answer(
            "❌ Ошибка: данные сессии потеряны.\n\n"
            "Начните процесс заново командой /recover_account"
        )
        await state.clear()
        return

    # Build message that should have been signed
    message_to_verify = f"Account Recovery: {recovery_code}\nWallet: {wallet_address}"

    recovery_service = AccountRecoveryService(session)

    # Verify signature
    is_valid, user = await recovery_service.verify_wallet_ownership(
        wallet_address, signature, message_to_verify
    )

    if not is_valid or not user:
        logger.warning(
            f"R16-3: Wallet ownership verification failed: "
            f"wallet={wallet_address}, "
            f"telegram_id={message.from_user.id if message.from_user else None}"
        )
        await message.answer(
            "❌ Не удалось подтвердить владение кошельком.\n\n"
            "**Возможные причины:**\n"
            "• Неправильная подпись\n"
            "• Сообщение было изменено перед подписанием\n"
            "• Использован неправильный приватный ключ\n\n"
            "Попробуйте еще раз или обратитесь в поддержку."
        )
        return
    
    logger.info(
        f"R16-3: Wallet ownership verified: user_id={user.id}, "
        f"wallet={wallet_address}, "
        f"new_telegram_id={message.from_user.id if message.from_user else None}"
    )

    # Check if new telegram_id is already in use
    new_telegram_id = message.from_user.id if message.from_user else None
    if not new_telegram_id:
        await message.answer("❌ Ошибка: не удалось определить ваш Telegram ID")
        await state.clear()
        return

    # Check if this telegram_id is already linked to another account
    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository(session)
    existing_user = await user_repo.find_by_telegram_id(new_telegram_id)

    if existing_user and existing_user.id != user.id:
        logger.warning(
            f"R16-3: Account recovery blocked - telegram_id already in use: "
            f"new_telegram_id={new_telegram_id}, "
            f"existing_user_id={existing_user.id}, "
            f"recovery_user_id={user.id}"
        )
        await message.answer(
            "❌ Этот Telegram аккаунт уже привязан к другому пользователю.\n\n"
            "Используйте другой Telegram аккаунт для восстановления."
        )
        await state.clear()
        return

    # Ask for additional verification (optional)
    text = (
        "✅ **Владение кошельком подтверждено!**\n\n"
        "Для дополнительной безопасности вы можете указать:\n"
        "• Email (если был указан при регистрации)\n"
        "• Телефон (если был указан при регистрации)\n\n"
        "Или отправьте /skip чтобы пропустить этот шаг."
    )

    await state.set_state(AccountRecoveryStates.waiting_for_additional_info)
    await state.update_data(user_id=user.id, signature=signature)
    await message.answer(text, parse_mode="Markdown")


@router.message(AccountRecoveryStates.waiting_for_additional_info)
async def handle_additional_info(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Handle additional verification info or skip.

    R16-3: Optional email/phone verification before account migration.
    """
    user_input = message.text.strip().lower()

    # Get data from state
    state_data = await state.get_data()
    wallet_address = state_data.get("wallet_address")
    signature = state_data.get("signature")
    recovery_code = state_data.get("recovery_code")
    user_id = state_data.get("user_id")

    if not wallet_address or not signature or not user_id:
        await message.answer(
            "❌ Ошибка: данные сессии потеряны.\n\n"
            "Начните процесс заново командой /recover_account"
        )
        await state.clear()
        return

    # Build message for recovery
    message_to_verify = f"Account Recovery: {recovery_code}\nWallet: {wallet_address}"

    additional_info = None

    # Check if user wants to skip
    if user_input == "/skip":
        additional_info = None
    else:
        # Try to parse email or phone
        if "@" in user_input:
            additional_info = {"email": user_input}
        elif user_input.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            additional_info = {"phone": user_input}
        else:
            await message.answer(
                "❌ Неверный формат.\n\n"
                "Укажите email (например: user@example.com) "
                "или телефон (например: +1234567890), "
                "или отправьте /skip чтобы пропустить."
            )
            return

    recovery_service = AccountRecoveryService(session)

    # Initiate recovery
    # Note: initiate_recovery returns (success, user, new_finpass_or_error)
    # When success=True: third element is new_finpass
    # When success=False: third element is error_message
    result = await recovery_service.initiate_recovery(
        new_telegram_id=message.from_user.id if message.from_user else None,
        wallet_address=wallet_address,
        signature=signature,
        message=message_to_verify,
        additional_info=additional_info,
    )

    success, user, third_value = result

    if not success or not user:
        error_message = third_value  # When success=False, third_value is error_message
        await message.answer(
            f"❌ Ошибка восстановления: {error_message or 'Неизвестная ошибка'}\n\n"
            "Обратитесь в поддержку для получения помощи."
        )
        await state.clear()
        return

    # When success=True, third_value is new_finpass
    new_finpass = third_value

    text = (
        "✅ **Аккаунт успешно восстановлен!**\n\n"
        f"Ваш аккаунт был привязан к новому Telegram ID: `{message.from_user.id if message.from_user else 'N/A'}`\n\n"
        f"**Новый финансовый пароль:**\n"
        f"```\n{new_finpass}\n```\n\n"
        "⚠️ **Важно:**\n"
        "• Сохраните этот пароль в безопасном месте\n"
        "• Старый Telegram аккаунт был заблокирован\n"
        "• Все ваши средства и депозиты сохранены\n\n"
        "Теперь вы можете использовать все функции бота."
    )

    await message.answer(text, parse_mode="Markdown")
    await state.clear()

    # Show main menu
    from app.repositories.blacklist_repository import BlacklistRepository

    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = await blacklist_repo.find_by_telegram_id(
        message.from_user.id if message.from_user else None
    )

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu_reply_keyboard(
            user=user, blacklist_entry=blacklist_entry, is_admin=False
        ),
    )

    logger.info(
        f"Account recovery completed: user {user.id}, "
        f"new_telegram_id={message.from_user.id if message.from_user else None}"
    )

