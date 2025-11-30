"""
Wallet management handler.

Allows admins to manage system and payout wallets.
"""

import re
from typing import Any

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.wallet_admin_service import WalletAdminService
from bot.keyboards.reply import admin_keyboard, get_admin_keyboard_from_data

router = Router()


@router.message(F.text == "💼 Управление кошельками")
async def show_wallet_management(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show wallet management menu."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    from app.config.settings import settings

    wallet_service = WalletAdminService(session)
    pending_requests = await wallet_service.get_pending_requests()

    text = (
        "💼 **Управление кошельками**\n\n"
        "**Текущие адреса:**\n"
        f"🏦 System: `{settings.system_wallet_address}`\n"
        f"💸 Payout: `{settings.payout_wallet_address}`\n\n"
    )

    if pending_requests:
        text += (
            f"⏳ Ожидающих запросов: {len(pending_requests)}\n\n"
            "Для просмотра заявок введите: **заявки кошельков**\n"
            "Для одобрения заявки введите: **одобрить кошелек <ID>**\n"
            "Для отклонения заявки введите: **отклонить кошелек <ID>**\n"
        )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )


@router.message(F.text == "⏳ Заявки кошельков")
async def show_wallet_requests(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show pending wallet change requests."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    wallet_service = WalletAdminService(session)
    requests = await wallet_service.get_pending_requests()

    if not requests:
        await message.answer(
            "⏳ **Запросы на изменение кошельков**\n\n"
            "Нет ожидающих запросов.",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    text = (
        "⏳ **Запросы на изменение кошельков**\n\n"
    )

    for req in requests:
        text += (
            f"ID: #{req.id}\n"
            f"Тип: {req.wallet_type}\n"
            f"Новый адрес: `{req.new_address}`\n"
            f"Запросил: {req.requested_by_admin_id}\n"
            f"Причина: {req.reason}\n\n"
        )

    text += (
        "Для одобрения заявки введите: **одобрить кошелек <ID>**\n"
        "Для отклонения заявки введите: **отклонить кошелек <ID>**\n"
        "Пример: `одобрить кошелек 123` или `отклонить кошелек 123`"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard(),
    )


@router.message(F.text.regexp(r"^одобрить кошелек\s+(\d+)$", flags=0))
async def approve_wallet_change(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Approve wallet change request."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract request ID from message text
    match = re.match(
        r"^одобрить кошелек\s+(\d+)$", message.text.strip(), re.IGNORECASE
    )
    if not match:
        await message.answer(
            "❌ Неверный формат. Используйте: `одобрить кошелек <ID>`",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    request_id = int(match.group(1))

    # Get admin
    from app.repositories.admin_repository import AdminRepository
    
    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by(telegram_id=message.from_user.id)
    
    if not admin:
        await message.answer(
            "❌ Администратор не найден",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    wallet_service = WalletAdminService(session)

    try:
        await wallet_service.approve_request(
            request_id=request_id,
            admin_id=admin.id,
            admin_notes="Approved via Telegram bot",
        )

        await session.commit()

        await message.answer(
            f"✅ Запрос #{request_id} одобрен!\n"
            f"⚠️ Требуется обновить конфигурацию и перезапустить бота.",
            reply_markup=get_admin_keyboard_from_data(data),
        )

        # Refresh display
        await show_wallet_requests(message, session, **data)

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {e}",
            reply_markup=get_admin_keyboard_from_data(data),
        )


@router.message(F.text.regexp(r"^отклонить кошелек\s+(\d+)$", flags=0))
async def reject_wallet_change(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Reject wallet change request."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract request ID from message text
    match = re.match(
        r"^отклонить кошелек\s+(\d+)$", message.text.strip(), re.IGNORECASE
    )
    if not match:
        await message.answer(
            "❌ Неверный формат. Используйте: `отклонить кошелек <ID>`",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    request_id = int(match.group(1))

    # Get admin
    from app.repositories.admin_repository import AdminRepository
    
    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by(telegram_id=message.from_user.id)
    
    if not admin:
        await message.answer(
            "❌ Администратор не найден",
            reply_markup=get_admin_keyboard_from_data(data),
        )
        return

    wallet_service = WalletAdminService(session)

    try:
        await wallet_service.reject_request(
            request_id=request_id,
            admin_id=admin.id,
            admin_notes="Rejected via Telegram bot",
        )

        await session.commit()

        await message.answer(
            f"✅ Запрос #{request_id} отклонён",
            reply_markup=get_admin_keyboard_from_data(data),
        )

        # Refresh display
        await show_wallet_requests(message, session, **data)

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {e}",
            reply_markup=get_admin_keyboard_from_data(data),
        )
