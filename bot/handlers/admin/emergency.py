"""
Admin emergency stop handler.

R17-3: Allows super_admin to toggle emergency stop flags for
deposits, withdrawals and ROI accruals.
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.global_settings_repository import GlobalSettingsRepository
from bot.keyboards.reply import get_admin_keyboard_from_data

router = Router()


def _format_status_flag(enabled: bool) -> str:
    return "⏸ Остановлено" if enabled else "▶ Активно"


@router.message(F.text == "🚨 Аварийные стопы")
async def show_emergency_menu(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """
    Show emergency stop status and basic instructions.

    Only super_admins are allowed to change flags. Basic/extended admins
    могут видеть только статусы через другие отчёты.
    """
    is_admin = data.get("is_admin", False)
    is_super_admin = data.get("is_super_admin", False)

    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    if not is_super_admin:
        await message.answer(
            "❌ Доступ к управлению аварийными стопами есть только у супер-админа."
        )
        return

    repo = GlobalSettingsRepository(session)
    settings = await repo.get_settings()

    text = (
        "🚨 **Аварийные стопы платформы**\n\n"
        "Используйте эти флаги только при инцидентах (ошибка блокчейна, "
        "подозрение на взлом, критические баги).\n\n"
        f"💰 Депозиты: {_format_status_flag(settings.emergency_stop_deposits)}\n"
        f"💸 Выводы: {_format_status_flag(settings.emergency_stop_withdrawals)}\n"
        f"📈 Начисление ROI: {_format_status_flag(settings.emergency_stop_roi)}\n\n"
        "Для изменения статусов используйте предусмотренные команды или меню "
        "в специальном разделе настроек (будет расширено в следующих итерациях).\n\n"
        "Сейчас аварийные стопы также можно переключать через конфигурацию "
        "окружения (переменные EMERGENCY_STOP_* в .env)."
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard_from_data(data),
    )


