"""
Admin Users Handler
Handles user management (ban/unban)
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from bot.states.admin_states import AdminStates

router = Router(name="admin_users")


def get_cancel_button() -> InlineKeyboardMarkup:
    """Get cancel button keyboard"""
    buttons = [
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")]
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
                callback_data="admin_block_user",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚠️ Терминировать аккаунт",
                callback_data="admin_terminate_user",
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


@router.callback_query(F.data == "admin_block_user")
async def handle_start_block_user(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool = False,
) -> None:
    """Start block user flow"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_block)

    message = """
🚫 **Блокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для блокировки.

Пользователь получит уведомление и сможет подать апелляцию в течение 3
    рабочих дней.

Пример: `@username` или `123456789`
    """.strip()

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_terminate_user")
async def handle_start_terminate_user(
    callback: CallbackQuery,
    state: FSMContext,
    is_admin: bool = False,
) -> None:
    """Start terminate user flow"""
    if not is_admin:
        await callback.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_terminate)

    message = """
⚠️ **Терминация аккаунта**

Отправьте username (с @) или Telegram ID пользователя для терминации.

⚠️ **ВНИМАНИЕ:** Аккаунт будет полностью заблокирован без возможности апелляции.

Пример: `@username` или `123456789`
    """.strip()

    await callback.message.edit_text(
        message, parse_mode="Markdown", reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.message(AdminStates.awaiting_user_to_block)
async def handle_block_user_input(  # noqa: C901
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle block user input"""
    if not is_admin:
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    from loguru import logger

    from app.models.blacklist import BlacklistActionType
    from app.services.blacklist_service import BlacklistService

    user_service = UserService(session)
    blacklist_service = BlacklistService(session)

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
        user = await user_service.get_by_telegram_id(telegram_id)
    else:
        try:
            telegram_id = int(identifier)
            user = await user_service.get_by_telegram_id(telegram_id)
        except ValueError:
            user = None

    if not user:
        await message.reply("❌ Пользователь не найден")
        await state.clear()
        return

    # Get admin ID
    admin_id = None
    try:
        from app.repositories.admin_repository import AdminRepository

        admin_repo = AdminRepository(session)
        admin = await admin_repo.get_by(telegram_id=message.from_user.id)
        if admin:
            admin_id = admin.id
    except Exception:
        pass

    # Add to blacklist with BLOCKED action
    try:
        await blacklist_service.add_to_blacklist(
            telegram_id=user.telegram_id,
            reason="Блокировка администратором",
            added_by_admin_id=admin_id,
            action_type=BlacklistActionType.BLOCKED,
        )

        # Mark user as banned
        user.is_banned = True
        await session.commit()

        # Send notification to user
        try:
            from aiogram import Bot

            from app.config.settings import settings

            bot = Bot(token=settings.telegram_bot_token)
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    "Здравствуйте, по решению участников нашего сообщества "
                    "за недопустимые высказывания и нарушение правил"
                        "поведения "
                    "в нашем сообществе ваш аккаунт заблокирован. "
                    "Вы можете подать апелляцию в течение 3 рабочих дней. "
                    "Ваша апелляция будет рассмотрена в течение 5"
                        "рабочих дней."
                ),
            )
            await bot.session.close()
        except Exception as e:
            logger.warning(
                f"Failed to send notification to user {user.telegram_id}: {e}"
            )

        display_name = user.username or f"ID {user.telegram_id}"
        await message.reply(
            f"✅ Пользователь {display_name} заблокирован.\n"
            f"Уведомление отправлено пользователю."
        )
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")

    # Reset state
    await state.clear()


@router.message(AdminStates.awaiting_user_to_terminate)
async def handle_terminate_user_input(  # noqa: C901
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    is_admin: bool = False,
) -> None:
    """Handle terminate user input"""
    if not is_admin:
        return

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

    from loguru import logger

    from app.models.blacklist import BlacklistActionType
    from app.services.blacklist_service import BlacklistService

    user_service = UserService(session)
    blacklist_service = BlacklistService(session)

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
        user = await user_service.get_by_telegram_id(telegram_id)
    else:
        try:
            telegram_id = int(identifier)
            user = await user_service.get_by_telegram_id(telegram_id)
        except ValueError:
            user = None

    if not user:
        await message.reply("❌ Пользователь не найден")
        await state.clear()
        return

    # Get admin ID
    admin_id = None
    try:
        from app.repositories.admin_repository import AdminRepository

        admin_repo = AdminRepository(session)
        admin = await admin_repo.get_by(telegram_id=message.from_user.id)
        if admin:
            admin_id = admin.id
    except Exception:
        pass

    # Add to blacklist with TERMINATED action
    try:
        await blacklist_service.add_to_blacklist(
            telegram_id=user.telegram_id,
            reason="Терминация администратором",
            added_by_admin_id=admin_id,
            action_type=BlacklistActionType.TERMINATED,
        )

        # Mark user as banned
        user.is_banned = True
        await session.commit()

        # Send notification to user
        try:
            from aiogram import Bot

            from app.config.settings import settings

            bot = Bot(token=settings.telegram_bot_token)
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    "Здравствуйте, по решению участников нашего сообщества "
                    "за недопустимые высказывания и нарушение правил"
                        "поведения "
                    "в нашем сообществе ваш аккаунт терминирован."
                ),
            )
            await bot.session.close()
        except Exception as e:
            logger.warning(
                f"Failed to send notification to user {user.telegram_id}: {e}"
            )

        display_name = user.username or f"ID {user.telegram_id}"
        await message.reply(
            f"✅ Аккаунт {display_name} терминирован.\n"
            f"Уведомление отправлено пользователю."
        )
    except Exception as e:
        logger.error(f"Error terminating user: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")

    # Reset state
    await state.clear()


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

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

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

    # Check if message is a menu button - if so, clear state and ignore
    from bot.utils.menu_buttons import is_menu_button

    if message.text and is_menu_button(message.text):
        await state.clear()
        return  # Let menu handlers process this

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
