"""
Admin Users Handler
Handles user management (ban/unban)
"""

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.services.admin_log_service import AdminLogService
from app.services.user_service import UserService
from bot.keyboards.reply import admin_users_keyboard, cancel_keyboard
from bot.states.admin_states import AdminStates

router = Router(name="admin_users")


@router.message(F.text == "🚫 Заблокировать пользователя")
async def handle_start_block_user(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start block user flow"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_block)

    text = """
🚫 **Блокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для блокировки.

Пользователь получит уведомление и сможет подать апелляцию "
        "в течение 3 рабочих дней."

Пример: `@username` или `123456789`
    """.strip()

    await message.answer(
        text, parse_mode="Markdown", reply_markup=cancel_keyboard()
    )


@router.message(F.text == "⚠️ Терминировать аккаунт")
async def handle_start_terminate_user(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start terminate user flow"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_terminate)

    text = """
⚠️ **Терминация аккаунта**

Отправьте username (с @) или Telegram ID пользователя для терминации.

⚠️ **ВНИМАНИЕ:** Аккаунт будет полностью заблокирован без возможности апелляции.

Пример: `@username` или `123456789`
    """.strip()

    await message.answer(
        text, parse_mode="Markdown", reply_markup=cancel_keyboard()
    )


@router.message(AdminStates.awaiting_user_to_block)
async def handle_block_user_input(  # noqa: C901
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle block user input"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ Блокировка отменена.",
            reply_markup=admin_users_keyboard(),
        )
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

        # Send notification to user with customizable text and keyboard
        try:
            from aiogram import Bot

            from app.config.settings import settings
            from app.repositories.blacklist_repository import (
                BlacklistRepository,
            )
            from app.repositories.system_setting_repository import (
                SystemSettingRepository,
            )
            from bot.keyboards.reply import main_menu_reply_keyboard

            bot = Bot(token=settings.telegram_bot_token)

            # Get customizable notification text
            setting_repo = SystemSettingRepository(session)
            notification_text = await setting_repo.get_value(
                "blacklist_block_notification_text",
                default=(
                    "⚠️ Ваш аккаунт временно заблокирован в нашем сообществе. "
                    "Вы можете подать апелляцию в течение 3 рабочих дней."
                )
            )

            # Add appeal instruction to notification text
            notification_text_with_instruction = (
                f"{notification_text}\n\n"
                "Чтобы подать апелляцию, нажмите кнопку "
                "'📝 Подать апелляцию' в боте."
            )

            # Send notification text
            await bot.send_message(
                chat_id=user.telegram_id,
                text=notification_text_with_instruction,
            )

            # Send keyboard with appeal button
            blacklist_repo = BlacklistRepository(session)
            blacklist_entry = await blacklist_repo.find_by_telegram_id(
                user.telegram_id
            )
            await bot.send_message(
                chat_id=user.telegram_id,
                text="Выберите действие:",
                reply_markup=main_menu_reply_keyboard(
                    user=user, blacklist_entry=blacklist_entry, is_admin=False
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
            f"Уведомление отправлено пользователю.",
            reply_markup=admin_users_keyboard(),
        )

        # Log admin action
        admin: Admin | None = data.get("admin")
        if admin:
            log_service = AdminLogService(session)
            await log_service.log_user_blocked(
                admin=admin,
                user_id=user.id,
                user_telegram_id=user.telegram_id,
                reason="Блокировка администратором",
            )
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        await message.reply(
            f"❌ Ошибка: {str(e)}",
            reply_markup=admin_users_keyboard(),
        )

    # Reset state
    await state.clear()


@router.message(AdminStates.awaiting_user_to_terminate)
async def handle_terminate_user_input(  # noqa: C901
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle terminate user input"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ Терминация отменена.",
            reply_markup=admin_users_keyboard(),
        )
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

        # Send notification to user with customizable text
        try:
            from aiogram import Bot

            from app.config.settings import settings
            from app.repositories.system_setting_repository import (
                SystemSettingRepository,
            )

            bot = Bot(token=settings.telegram_bot_token)

            # Get customizable notification text
            setting_repo = SystemSettingRepository(session)
            notification_text = await setting_repo.get_value(
                "blacklist_terminate_notification_text",
                default=(
                    "❌ Ваш аккаунт терминирован в нашем сообществе "
                    "без возможности восстановления."
                )
            )

            await bot.send_message(
                chat_id=user.telegram_id,
                text=notification_text,
            )
            await bot.session.close()
        except Exception as e:
            logger.warning(
                f"Failed to send notification to user {user.telegram_id}: {e}"
            )

        display_name = user.username or f"ID {user.telegram_id}"
        await message.reply(
            f"✅ Аккаунт {display_name} терминирован.\n"
            f"Уведомление отправлено пользователю.",
            reply_markup=admin_users_keyboard(),
        )

        # Log admin action
        admin: Admin | None = data.get("admin")
        if admin:
            log_service = AdminLogService(session)
            await log_service.log_user_terminated(
                admin=admin,
                user_id=user.id,
                user_telegram_id=user.telegram_id,
                reason="Терминация администратором",
            )
    except Exception as e:
        logger.error(f"Error terminating user: {e}")
        await message.reply(
            f"❌ Ошибка: {str(e)}",
            reply_markup=admin_users_keyboard(),
        )

    # Reset state
    await state.clear()


@router.message(AdminStates.awaiting_user_to_ban)
async def handle_ban_user_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle ban user input"""
    is_admin = data.get("is_admin", False)
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

    if result and result.get("success"):
        display_name = user.username or f"ID {user.telegram_id}"
        await message.reply(
            f"✅ Пользователь {display_name} заблокирован",
            reply_markup=admin_users_keyboard(),
        )
    else:
        error = result.get("error", "Unknown") if result else "Unknown error"
        await message.reply(
            f"❌ Ошибка: {error}",
            reply_markup=admin_users_keyboard(),
        )

    # Reset state
    await state.clear()


@router.message(F.text == "✅ Разблокировать пользователя")
async def handle_start_unban_user(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start unban user flow"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    await state.set_state(AdminStates.awaiting_user_to_unban)

    text = """
✅ **Разблокировка пользователя**

Отправьте username (с @) или Telegram ID пользователя для разблокировки.

Пример: `@username` или `123456789`
    """.strip()

    await message.answer(
        text, parse_mode="Markdown", reply_markup=cancel_keyboard()
    )


@router.message(AdminStates.awaiting_user_to_unban)
async def handle_unban_user_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Handle unban user input"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        return

    # Check if message is a cancel button
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "❌ Разблокировка отменена.",
            reply_markup=admin_users_keyboard(),
        )
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
        user = await user_service.get_by_telegram_id(telegram_id)

    if not user:
        await message.reply("❌ Пользователь не найден")
        return

    # Unban user
    result = await user_service.unban_user(user.id)

    if result["success"]:
        display_name = user.username or f"ID {user.telegram_id}"
        await message.reply(
            f"✅ Пользователь {display_name} разблокирован",
            reply_markup=admin_users_keyboard(),
        )
    else:
        await message.reply(
            f"❌ Ошибка: {result.get('error', 'Unknown')}",
            reply_markup=admin_users_keyboard(),
        )

    # Reset state
    await state.clear()


@router.message(F.text == "🔍 Найти пользователя")
async def handle_find_user(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    """Start find user flow"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # For now, just show a message - can be extended with FSM state if needed
    await message.answer(
        "🔍 **Поиск пользователя**\n\n"
        "Отправьте username (с @) или Telegram ID пользователя для поиска.\n\n"
        "Пример: `@username` или `123456789`",
        parse_mode="Markdown",
        reply_markup=admin_users_keyboard(),
    )


@router.message(F.text == "👥 Список пользователей")
async def handle_list_users(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Show list of users"""
    is_admin = data.get("is_admin", False)
    if not is_admin:
        await message.answer("❌ Эта функция доступна только администраторам")
        return

    # Get recent users (last 10) ordered by created_at desc
    from sqlalchemy import desc, select

    from app.models.user import User

    stmt = select(User).order_by(desc(User.created_at)).limit(10)
    result = await session.execute(stmt)
    users = result.scalars().all()

    if not users:
        await message.answer(
            "👥 **Список пользователей**\n\nПользователи не найдены.",
            reply_markup=admin_users_keyboard(),
        )
        return

    text = "👥 **Последние пользователи:**\n\n"
    for idx, user in enumerate(users, 1):
        text += f"{idx}. {user.username or f'ID {user.telegram_id}'}\n"
        text += f"   ID: {user.telegram_id}\n"
        text += f"   Баланс: {user.balance:.2f} USDT\n\n"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_users_keyboard(),
    )


@router.message(F.text == "👑 Админ-панель")
async def handle_back_to_admin_panel(
    message: Message,
    session: AsyncSession,
    **data: Any,
) -> None:
    """Return to admin panel from users menu"""
    from bot.handlers.admin.panel import handle_admin_panel_button

    await handle_admin_panel_button(message, session, **data)
