"""
Inline keyboards for bot.

Contains inline keyboard builders for various bot features.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_to_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """
    Back to admin panel keyboard.

    Returns:
        InlineKeyboardMarkup with back button
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в админ-панель",
            callback_data="back_to_admin_panel",
        )
    )
    return builder.as_markup()


def paginated_user_messages_keyboard(
    telegram_id: int,
    page: int,
    total: int,
    page_size: int = 50,
) -> InlineKeyboardMarkup:
    """
    Paginated user messages keyboard.

    Args:
        telegram_id: User telegram ID
        page: Current page (0-indexed)
        total: Total messages count
        page_size: Messages per page

    Returns:
        InlineKeyboardMarkup with pagination
    """
    builder = InlineKeyboardBuilder()

    total_pages = (total + page_size - 1) // page_size

    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"user_messages_page:{telegram_id}:{page - 1}",
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"user_messages_page:{telegram_id}:{page + 1}",
            )
        )

    builder.row(*nav_buttons)

    # Delete button (only for super admin)
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить все сообщения",
            callback_data=f"delete_user_messages:{telegram_id}",
        )
    )

    # Back button
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в админ-панель",
            callback_data="back_to_admin_panel",
        )
    )

    return builder.as_markup()


def master_key_management_keyboard() -> InlineKeyboardMarkup:
    """
    Master key management keyboard.

    Returns:
        InlineKeyboardMarkup with master key options
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔍 Показать текущий ключ",
            callback_data="show_master_key",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Сгенерировать новый ключ",
            callback_data="generate_new_master_key",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад в главное меню",
            callback_data="back_to_main_menu",
        )
    )

    return builder.as_markup()

