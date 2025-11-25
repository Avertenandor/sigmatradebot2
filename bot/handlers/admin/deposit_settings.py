"""
Deposit settings handler.

Allows admins to configure max open deposit level and manage level availability.
R17-2: Temporary level deactivation via is_active flag.
"""

import re
from typing import Any

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from app.repositories.global_settings_repository import GlobalSettingsRepository
from app.services.admin_log_service import AdminLogService
from bot.keyboards.reply import admin_deposit_settings_keyboard

router = Router()


@router.message(F.text == "⚙️ Настроить уровни депозитов")
async def show_deposit_settings(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show deposit settings with level availability status."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    settings_repo = GlobalSettingsRepository(session)
    settings = await settings_repo.get_settings()
    max_level = settings.max_open_deposit_level

    # R17-2: Get level availability status
    version_repo = DepositLevelVersionRepository(session)
    levels_status = []
    for level_num in range(1, 6):
        current_version = await version_repo.get_current_version(level_num)
        if current_version:
            status = "✅ Активен" if current_version.is_active else "❌ Отключен"
            levels_status.append(f"{level_num}️⃣ Уровень {level_num}: {status}")
        else:
            levels_status.append(f"{level_num}️⃣ Уровень {level_num}: ⚠️ Не настроен")

    text = (
        "⚙️ **Настройки депозитов**\n\n"
        f"Максимальный открытый уровень: **{max_level}**\n\n"
        "**Статус уровней:**\n"
        + "\n".join(levels_status)
        + "\n\n"
        "**Команды:**\n"
        "• `уровень <номер>` - установить максимальный уровень\n"
        "• `включить <номер>` - включить уровень\n"
        "• `отключить <номер>` - отключить уровень\n"
        "• `статус уровней` - показать статус всех уровней\n\n"
        "Примеры:\n"
        "• `уровень 3`\n"
        "• `включить 2`\n"
        "• `отключить 5`"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_settings_keyboard(),
    )


@router.message(F.text.regexp(r"^уровень\s+(\d+)$", flags=0))
async def set_max_deposit_level(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Set max deposit level."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract level from message text
    match = re.match(r"^уровень\s+(\d+)$", message.text.strip(), re.IGNORECASE)
    if not match:
        await message.answer(
            "❌ Неверный формат. Используйте: `уровень <номер>` (1-5)",
            reply_markup=admin_deposit_settings_keyboard(),
        )
        return

    level = int(match.group(1))
    
    if level < 1 or level > 5:
        await message.answer(
            "❌ Уровень должен быть от 1 до 5",
            reply_markup=admin_deposit_settings_keyboard(),
        )
        return

    # Get admin
    from app.repositories.admin_repository import AdminRepository
    
    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by(telegram_id=message.from_user.id)
    
    if not admin:
        await message.answer(
            "❌ Администратор не найден",
            reply_markup=admin_deposit_settings_keyboard(),
        )
        return

    settings_repo = GlobalSettingsRepository(session)
    await settings_repo.update_settings(max_open_deposit_level=level)
    await session.commit()

    await message.answer(
        f"✅ Максимальный уровень установлен: {level}",
        reply_markup=admin_deposit_settings_keyboard(),
    )

    # Refresh display
    await show_deposit_settings(message, session, **data)


@router.message(F.text.regexp(r"^(включить|отключить)\s+(\d+)$", flags=0))
async def toggle_level_availability(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Toggle level availability (R17-2)."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Extract action and level
    match = re.match(r"^(включить|отключить)\s+(\d+)$", message.text.strip(), re.IGNORECASE)
    if not match:
        await message.answer(
            "❌ Неверный формат. Используйте: `включить <номер>` или `отключить <номер>`",
            reply_markup=admin_deposit_settings_keyboard(),
        )
        return

    action = match.group(1).lower()
    level = int(match.group(2))

    if level < 1 or level > 5:
        await message.answer(
            "❌ Уровень должен быть от 1 до 5",
            reply_markup=admin_deposit_settings_keyboard(),
        )
        return

    # Get admin
    from app.repositories.admin_repository import AdminRepository

    admin_repo = AdminRepository(session)
    admin = await admin_repo.get_by(telegram_id=message.from_user.id)

    if not admin:
        await message.answer(
            "❌ Администратор не найден",
            reply_markup=admin_deposit_settings_keyboard(),
        )
        return

    # Get current version
    version_repo = DepositLevelVersionRepository(session)
    current_version = await version_repo.get_current_version(level)

    if not current_version:
        await message.answer(
            f"❌ Уровень {level} не найден. Сначала создайте версию для этого уровня.",
            reply_markup=admin_deposit_settings_keyboard(),
        )
        return

    # Toggle is_active
    new_status = action == "включить"
    
    # Update version
    await version_repo.update(current_version.id, is_active=new_status)
    await session.commit()

    # Log admin action
    log_service = AdminLogService(session)
    await log_service.log_action(
        admin_id=admin.id,
        action_type="TOGGLE_DEPOSIT_LEVEL",
        details={
            "level": level,
            "action": action,
            "new_status": new_status,
            "version_id": current_version.id,
        },
    )
    await session.commit()

    status_text = "включен" if new_status else "отключен"
    await message.answer(
        f"✅ Уровень {level} {status_text}",
        reply_markup=admin_deposit_settings_keyboard(),
    )

    # Refresh display
    await show_deposit_settings(message, session, **data)


@router.message(F.text == "📊 Статус уровней")
@router.message(F.text.regexp(r"^статус\s+уровней$", flags=0))
async def show_level_status(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show detailed status of all levels (R17-2)."""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    version_repo = DepositLevelVersionRepository(session)
    
    status_lines = []
    for level_num in range(1, 6):
        current_version = await version_repo.get_current_version(level_num)
        if current_version:
            status_icon = "✅" if current_version.is_active else "❌"
            status_text = "Активен" if current_version.is_active else "Отключен"
            status_lines.append(
                f"{status_icon} **Уровень {level_num}**: {status_text}\n"
                f"   Сумма: {current_version.amount} USDT\n"
                f"   ROI: {current_version.roi_percent}%/день\n"
                f"   Кап: {current_version.roi_cap_percent}%\n"
                f"   Версия: {current_version.version}"
            )
        else:
            status_lines.append(f"⚠️ **Уровень {level_num}**: Не настроен")

    text = "📊 **Статус уровней депозитов**\n\n" + "\n\n".join(status_lines)

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_deposit_settings_keyboard(),
    )


@router.message(F.text == "👑 Админ-панель")
async def handle_back_to_admin_panel(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to admin panel from deposit settings menu"""
    from bot.handlers.admin.panel import handle_admin_panel_button
    
    await handle_admin_panel_button(message, session, **data)
