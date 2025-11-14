"""
Admin Users Handler
Handles user management (ban/unban)
"""

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from bot.states.admin_states import AdminStates


router = Router(name="admin_users")


def get_cancel_button() -> InlineKeyboardMarkup:
    """Get cancel button keyboard"""
    buttons = [
        [
            InlineKeyboardButton(
                text="❌ Отмена", callback_data="admin_panel"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_users")
async def handle_admin_users_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Show admin users management menu"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    buttons = [
        [
            InlineKeyboardButton(
                text="🚫 Заблокировать пользователя",
                callback_data="admin_ban_user",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✅ Разблокировать пользователя",
                callback_data="admin_unban_user",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Админ-панель", callback_data="admin_panel"
            ),
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    message = """
👥 **Управление пользователями**

Выберите действие:
    """.strip()

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "admin_ban_user")
async def handle_start_ban_user(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool = False,
) -> None:
    """Start ban user flow"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_ban)

    message = """
🚫 **Блокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для блокировки.

Пример: `@username` или `123456789`
    """.strip()

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.message(AdminStates.awaiting_user_to_ban)
async def handle_ban_user_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle ban user input"""
    if not is_admin:
        return

    user_service = UserService(session)

    identifier = message.text.strip() if message.text else ""

    if not identifier:
        await message.reply("❌ Отправьте username или ID")
        return

    # Find user
    user = None

    if identifier.startswith("@"):
        username = identifier[1:]
        user = await user_service.find_by_username(username)
    elif identifier.isdigit():
        telegram_id = int(identifier)
        user = await user_service.find_by_telegram_id(telegram_id)

    if not user:
        await message.reply("❌ Пользователь не найден")
        return

    # Ban user
    result = await user_service.ban_user(user.id)

    if result["success"]:
        display_name = user.username or f"ID {user.telegram_id}"
        await message.reply(f"✅ Пользователь {display_name} заблокирован")
    else:
        await message.reply(f"❌ Ошибка: {result.get('error', 'Unknown')}")

    # Reset state
    await state.clear()


@router.callback_query(F.data == "admin_unban_user")
async def handle_start_unban_user(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool = False,
) -> None:
    """Start unban user flow"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_unban)

    message = """
✅ **Разблокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для разблокировки.

Пример: `@username` или `123456789`
    """.strip()

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.message(AdminStates.awaiting_user_to_unban)
async def handle_unban_user_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle unban user input"""
    if not is_admin:
        return

    user_service = UserService(session)

    identifier = message.text.strip() if message.text else ""

    if not identifier:
        await message.reply("❌ Отправьте username или ID")
        return

    # Find user
    user = None

    if identifier.startswith("@"):
        username = identifier[1:]
        user = await user_service.find_by_username(username)
    elif identifier.isdigit():
        telegram_id = int(identifier)
        user = await user_service.find_by_telegram_id(telegram_id)

    if not user:
        await message.reply("❌ Пользователь не найден")
        return

    # Unban user
    result = await user_service.unban_user(user.id)

    if result["success"]:
        display_name = user.username or f"ID {user.telegram_id}"
        await message.reply(f"✅ Пользователь {display_name} разблокирован")
    else:
        await message.reply(f"❌ Ошибка: {result.get('error', 'Unknown')}")

    # Reset state
    await state.clear()
