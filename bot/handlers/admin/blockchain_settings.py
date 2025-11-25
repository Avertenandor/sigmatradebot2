"""
Admin blockchain settings handler.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.global_settings_repository import GlobalSettingsRepository
from app.services.blockchain_service import get_blockchain_service
from bot.keyboards.inline import admin_blockchain_keyboard

router = Router()


async def get_status_text() -> str:
    """Get formatted status text for blockchain settings."""
    bs = get_blockchain_service()
    # Force refresh local settings from DB just in case
    await bs.force_refresh_settings()

    status = await bs.get_providers_status()

    text = "📡 *Управление Блокчейном*\n\n"
    text += f"Текущий провайдер: *{bs.active_provider_name.upper()}*\n"
    text += f"Авто-смена: *{'ВКЛ' if bs.is_auto_switch_enabled else 'ВЫКЛ'}*\n\n"

    text += "*Статус провайдеров:*\n"
    for name, data in status.items():
        icon = "✅" if data.get("connected") else "❌"
        active_mark = " (ACTIVE)" if data.get("active") else ""
        block = data.get("block", "N/A")
        error = f" Error: {data.get('error')}" if data.get("error") else ""
        text += f"{icon} *{name.upper()}*{active_mark}: Block {block}{error}\n"

    return text


@router.message(F.text == "📡 Блокчейн Настройки")
async def show_blockchain_settings(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show blockchain settings menu."""
    text = await get_status_text()
    bs = get_blockchain_service()

    await message.answer(
        text,
        reply_markup=admin_blockchain_keyboard(
            bs.active_provider_name, bs.is_auto_switch_enabled
        ),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("blockchain_"))
async def handle_blockchain_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Handle blockchain settings callbacks."""
    action = callback.data
    repo = GlobalSettingsRepository(session)
    bs = get_blockchain_service()

    if action == "blockchain_refresh":
        # Just refresh
        pass

    elif action == "blockchain_set_quicknode":
        await repo.update_settings(active_rpc_provider="quicknode")
        await session.commit()
        await bs.force_refresh_settings()

    elif action == "blockchain_set_nodereal":
        await repo.update_settings(active_rpc_provider="nodereal")
        await session.commit()
        await bs.force_refresh_settings()

    elif action == "blockchain_toggle_auto":
        # First ensure we have latest settings
        await bs.force_refresh_settings()
        new_val = not bs.is_auto_switch_enabled
        await repo.update_settings(is_auto_switch_enabled=new_val)
        await session.commit()
        await bs.force_refresh_settings()

    # Update message
    text = await get_status_text()
    try:
        await callback.message.edit_text(
            text,
            reply_markup=admin_blockchain_keyboard(
                bs.active_provider_name, bs.is_auto_switch_enabled
            ),
            parse_mode="Markdown",
        )
    except Exception:
        # Ignore "message is not modified"
        pass

    await callback.answer()

