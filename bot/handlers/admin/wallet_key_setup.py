"""
Admin handler for secure wallet private key management.

ПОЛНОЕ УПРАВЛЕНИЕ приватными ключами через Telegram бота:
- Просмотр текущего кошелька
- Добавление/обновление ключа
- Удаление ключа
- Безопасное хранение
"""

import subprocess

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from eth_account import Account
from mnemonic import Mnemonic

from app.config.settings import settings

router = Router()


class WalletKeySetup(StatesGroup):
    """States for wallet key setup."""

    waiting_for_key = State()
    waiting_for_seed = State()
    confirming = State()
    confirming_removal = State()


@router.message(Command("setup_wallet_key"))
async def cmd_setup_wallet_key(message: Message, state: FSMContext):
    """
    Команда для настройки приватного ключа кошелька.

    Доступна только super admin.
    """
    # Проверка что пользователь - super admin
    admin_ids = settings.get_admin_ids()
    if not admin_ids or message.from_user.id != admin_ids[0]:
        await message.answer("❌ Команда доступна только super admin")
        return

    await message.answer(
        "🔐 <b>НАСТРОЙКА ПРИВАТНОГО КЛЮЧА КОШЕЛЬКА</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Это критически важная операция!\n\n"
        "📝 <b>Инструкция:</b>\n"
        "1. Отправьте приватный ключ в следующем сообщении\n"
        "2. Формат: 64 hex символа (без 0x) или с 0x\n"
        "3. Ваше сообщение будет немедленно удалено\n"
        "4. Ключ будет зашифрован и сохранён\n\n"
        "🔒 После сохранения бот автоматически перезапустится\n\n"
        "❌ Для отмены используйте /cancel",
        parse_mode="HTML",
    )

    await state.set_state(WalletKeySetup.waiting_for_key)


@router.message(WalletKeySetup.waiting_for_key)
async def process_wallet_key(message: Message, state: FSMContext):
    """
    Обработка приватного ключа от админа.
    """
    try:
        # Немедленно удаляем сообщение с ключом
        await message.delete()

        # Получаем ключ из сообщения
        private_key = message.text.strip()

        # Удаляем префикс 0x если есть
        if private_key.startswith("0x"):
            private_key = private_key[2:]

        # Валидация: проверяем что это hex и 64 символа
        if len(private_key) != 64:
            await message.answer(
                "❌ Неверная длина ключа!\n"
                f"Получено: {len(private_key)} символов\n"
                "Требуется: 64 hex символа\n\n"
                "Попробуйте ещё раз или /cancel для отмены"
            )
            return

        try:
            int(private_key, 16)  # Проверка что это hex
        except ValueError:
            await message.answer(
                "❌ Ключ содержит недопустимые символы!\n"
                "Разрешены только: 0-9, a-f, A-F\n\n"
                "Попробуйте ещё раз или /cancel для отмены"
            )
            return

        # Валидация через eth_account
        try:
            account = Account.from_key(private_key)
            wallet_address = account.address
        except Exception as e:
            await message.answer(
                f"❌ Неверный приватный ключ!\n"
                f"Ошибка: {str(e)}\n\n"
                "Попробуйте ещё раз или /cancel для отмены"
            )
            return

        # Сохраняем ключ и адрес в state для подтверждения
        await state.update_data(
            private_key=private_key, wallet_address=wallet_address
        )

        await message.answer(
            f"✅ <b>Ключ валиден!</b>\n\n"
            f"🔑 <b>Адрес кошелька:</b>\n"
            f"<code>{wallet_address}</code>\n\n"
            f"⚠️ <b>Текущий адрес в конфиге:</b>\n"
            f"<code>{settings.wallet_address}</code>\n\n"
            "❓ Подтвердите сохранение:\n"
            "• Ключ будет сохранён в .env\n"
            "• Бот будет перезапущен\n"
            "• Blockchain операции будут использовать этот кошелёк\n\n"
            "Используйте /confirm для подтверждения или /cancel для отмены",
            parse_mode="HTML",
        )

        await state.set_state(WalletKeySetup.confirming)

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при обработке ключа:\n{str(e)}\n\n"
            "Попробуйте ещё раз или /cancel для отмены"
        )
        await state.clear()


@router.message(Command("confirm"), WalletKeySetup.confirming)
async def confirm_wallet_key(message: Message, state: FSMContext):
    """
    Подтверждение и сохранение приватного ключа.
    """
    data = await state.get_data()
    private_key = data.get("private_key")
    wallet_address = data.get("wallet_address")

    if not private_key or not wallet_address:
        await message.answer(
            "❌ Ошибка: данные потеряны. Начните заново с /setup_wallet_key"
        )
        await state.clear()
        return

    try:
        # Путь к .env файлу
        env_file = "/opt/sigmatradebot/.env"

        # Читаем текущий .env
        with open(env_file) as f:
            env_lines = f.readlines()

        # Обновляем wallet_private_key и wallet_address
        updated = False
        updated_address = False
        new_lines = []

        for line in env_lines:
            if line.startswith("wallet_private_key="):
                new_lines.append(f"wallet_private_key={private_key}\n")
                updated = True
            elif line.startswith("wallet_address="):
                new_lines.append(f"wallet_address={wallet_address}\n")
                updated_address = True
            else:
                new_lines.append(line)

        # Если переменная не найдена, добавляем в конец
        if not updated:
            new_lines.append("\n# Wallet Private Key (updated via Telegram)\n")
            new_lines.append(f"wallet_private_key={private_key}\n")
        if not updated_address:
            new_lines.append(f"wallet_address={wallet_address}\n")

        # Записываем обновлённый .env
        with open(env_file, "w") as f:
            f.writelines(new_lines)

        await message.answer(
            "✅ <b>Приватный ключ успешно сохранён!</b>\n\n"
            f"🔑 Адрес: <code>{wallet_address}</code>\n\n"
            "🔄 Перезапускаю бота для применения изменений...",
            parse_mode="HTML",
        )

        # Очищаем state
        await state.clear()

        # Перезапускаем Docker контейнеры
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "/opt/sigmatradebot/docker-compose.python.yml",
                "restart",
                "bot",
                "worker",
                "scheduler",
            ],
            check=True,
            capture_output=True,
        )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при сохранении:\n{str(e)}\n\n"
            "Обратитесь к администратору сервера"
        )
        await state.clear()


@router.message(Command("cancel"), WalletKeySetup)
async def cancel_wallet_key_setup(message: Message, state: FSMContext):
    """
    Отмена настройки ключа.
    """
    await state.clear()
    await message.answer("❌ Операция отменена")


# ============================================
# НОВЫЕ КОМАНДЫ УПРАВЛЕНИЯ КОШЕЛЬКОМ
# ============================================


def get_wallet_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления кошельком."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статус кошелька", callback_data="wallet_status"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить/обновить ключ",
                    callback_data="wallet_add",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌱 Добавить seed фразу",
                    callback_data="wallet_add_seed",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить ключ", callback_data="wallet_remove"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть", callback_data="wallet_close"
                ),
            ],
        ]
    )
    return keyboard


@router.message(Command("wallet_menu"))
async def cmd_wallet_menu(message: Message):
    """
    Главное меню управления кошельком.

    Доступно только super admin.
    """
    # Проверка что пользователь - super admin
    admin_ids = settings.get_admin_ids()
    if not admin_ids or message.from_user.id != admin_ids[0]:
        await message.answer("❌ Команда доступна только super admin")
        return

    await message.answer(
        "🔐 <b>УПРАВЛЕНИЕ КОШЕЛЬКОМ</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_wallet_management_keyboard(),
    )


@router.callback_query(F.data == "wallet_status")
async def callback_wallet_status(callback: CallbackQuery):
    """Показать статус кошелька."""
    # Проверка прав
    admin_ids = settings.get_admin_ids()
    if not admin_ids or callback.from_user.id != admin_ids[0]:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    # Проверяем текущий ключ
    current_key = settings.wallet_private_key
    is_test_key = current_key == "0" * 64 or not current_key

    if is_test_key:
        status_text = (
            "⚠️ <b>СТАТУС КОШЕЛЬКА</b>\n\n"
            "🔴 <b>Статус:</b> Тестовый ключ\n"
            f"📍 <b>Адрес:</b> <code>{settings.wallet_address}</code>\n\n"
            "⚠️ <b>ВНИМАНИЕ!</b> Используется тестовый ключ!\n"
            "Blockchain операции не будут работать.\n\n"
            "💡 Установите реальный ключ через кнопку ниже."
        )
    else:
        try:
            # Валидация ключа
            account = Account.from_key(settings.wallet_private_key)
            actual_address = account.address

            # Проверка соответствия адресов
            if actual_address.lower() == settings.wallet_address.lower():
                match_status = "✅ Соответствует"
            else:
                match_status = (
                    f"⚠️ НЕ соответствует!\nФактический: "
                    f"<code>{actual_address}</code>"
                )

            status_text = (
                "✅ <b>СТАТУС КОШЕЛЬКА</b>\n\n"
                "🟢 <b>Статус:</b> Ключ установлен\n"
                f"📍 <b>Адрес в конфиге:</b>\n"
                f"<code>{settings.wallet_address}</code>\n\n"
                f"🔍 <b>Проверка:</b> {match_status}\n\n"
                "✅ Blockchain операции доступны"
            )
        except Exception as e:
            status_text = (
                "❌ <b>ОШИБКА КЛЮЧА</b>\n\n"
                "🔴 <b>Статус:</b> Неверный ключ\n"
                f"📍 <b>Адрес в конфиге:</b>"
                    "<code>{settings.wallet_address}</code>\n\n"
                f"⚠️ <b>Ошибка:</b> {str(e)}\n\n"
                "💡 Установите корректный ключ."
            )

    await callback.message.edit_text(
        status_text,
        parse_mode="HTML",
        reply_markup=get_wallet_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "wallet_add")
async def callback_wallet_add(callback: CallbackQuery, state: FSMContext):
    """Начать процесс добавления ключа."""
    # Проверка прав
    admin_ids = settings.get_admin_ids()
    if not admin_ids or callback.from_user.id != admin_ids[0]:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    await callback.message.edit_text(
        "🔐 <b>ДОБАВЛЕНИЕ ПРИВАТНОГО КЛЮЧА</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Это критически важная операция!\n\n"
        "📝 <b>Инструкция:</b>\n"
        "1. Отправьте приватный ключ в следующем сообщении\n"
        "2. Формат: 64 hex символа (без 0x) или с 0x\n"
        "3. Ваше сообщение будет немедленно удалено\n"
        "4. Ключ будет зашифрован и сохранён\n\n"
        "🔒 После сохранения бот автоматически перезапустится\n\n"
        "❌ Для отмены используйте /cancel",
        parse_mode="HTML",
    )

    await state.set_state(WalletKeySetup.waiting_for_key)
    await callback.answer()


@router.callback_query(F.data == "wallet_add_seed")
async def callback_wallet_add_seed(callback: CallbackQuery, state: FSMContext):
    """Начать процесс добавления seed фразы."""
    # Проверка прав
    admin_ids = settings.get_admin_ids()
    if not admin_ids or callback.from_user.id != admin_ids[0]:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    await callback.message.edit_text(
        "🌱 <b>ДОБАВЛЕНИЕ SEED ФРАЗЫ</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Это критически важная операция!\n\n"
        "📝 <b>Инструкция:</b>\n"
        "1. Отправьте seed фразу (mnemonic) в следующем сообщении\n"
        "2. Формат: 12 или 24 слова через пробел\n"
        "3. Ваше сообщение будет немедленно удалено\n"
        "4. Из seed фразы будет извлечён приватный ключ\n"
        "5. Ключ будет сохранён в .env\n\n"
        "🔒 После сохранения бот автоматически перезапустится\n\n"
        "❌ Для отмены используйте /cancel",
        parse_mode="HTML",
    )

    await state.set_state(WalletKeySetup.waiting_for_seed)
    await callback.answer()


@router.message(WalletKeySetup.waiting_for_seed)
async def process_wallet_seed(message: Message, state: FSMContext):
    """
    Обработка seed фразы от админа.
    """
    try:
        # Немедленно удаляем сообщение с seed фразой
        await message.delete()

        # Получаем seed фразу из сообщения
        seed_phrase = message.text.strip()

        # Валидация seed фразы
        try:
            mnemo = Mnemonic("english")
            if not mnemo.check(seed_phrase):
                await message.answer(
                    "❌ Неверная seed фраза!\n"
                    "Проверьте правильность написания слов.\n\n"
                    "Попробуйте ещё раз или /cancel для отмены"
                )
                return
        except Exception as e:
            await message.answer(
                f"❌ Ошибка валидации seed фразы!\n"
                f"Ошибка: {str(e)}\n\n"
                "Попробуйте ещё раз или /cancel для отмены"
            )
            return

        # Извлекаем приватный ключ из seed фразы
        try:
            Account.enable_unaudited_hdwallet_features()
            account = Account.from_mnemonic(seed_phrase)
            private_key = account.key.hex()
            wallet_address = account.address
        except Exception as e:
            await message.answer(
                f"❌ Ошибка при извлечении ключа из seed фразы!\n"
                f"Ошибка: {str(e)}\n\n"
                "Попробуйте ещё раз или /cancel для отмены"
            )
            return

        # Сохраняем ключ и адрес в state для подтверждения
        await state.update_data(
            private_key=private_key, wallet_address=wallet_address
        )

        await message.answer(
            f"✅ <b>Seed фраза валидна!</b>\n\n"
            f"🔑 <b>Адрес кошелька:</b>\n"
            f"<code>{wallet_address}</code>\n\n"
            f"⚠️ <b>Текущий адрес в конфиге:</b>\n"
            f"<code>{settings.wallet_address}</code>\n\n"
            "❓ Подтвердите сохранение:\n"
            "• Приватный ключ будет извлечён и сохранён в .env\n"
            "• Бот будет перезапущен\n"
            "• Blockchain операции будут использовать этот кошелёк\n\n"
            "Используйте /confirm для подтверждения или /cancel для отмены",
            parse_mode="HTML",
        )

        await state.set_state(WalletKeySetup.confirming)

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при обработке seed фразы:\n{str(e)}\n\n"
            "Попробуйте ещё раз или /cancel для отмены"
        )
        await state.clear()


@router.callback_query(F.data == "wallet_remove")
async def callback_wallet_remove(callback: CallbackQuery, state: FSMContext):
    """Начать процесс удаления ключа."""
    # Проверка прав
    admin_ids = settings.get_admin_ids()
    if not admin_ids or callback.from_user.id != admin_ids[0]:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    # Проверяем есть ли ключ
    current_key = settings.wallet_private_key
    is_test_key = current_key == "0" * 64 or not current_key

    if is_test_key:
        await callback.answer(
            "⚠️ Ключ уже удалён или не установлен", show_alert=True
        )
        return

    # Создаём клавиатуру подтверждения
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data="wallet_remove_confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="wallet_status"
                ),
            ]
        ]
    )

    await callback.message.edit_text(
        "🗑️ <b>УДАЛЕНИЕ ПРИВАТНОГО КЛЮЧА</b>\n\n"
        f"📍 <b>Текущий адрес:</b>\n<code>{settings.wallet_address}</code>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b>\n"
        "После удаления ключа:\n"
        "• Blockchain операции будут недоступны\n"
        "• Выплаты не будут работать\n"
        "• Ключ будет заменён на тестовый\n"
        "• Бот будет перезапущен\n\n"
        "❓ Вы уверены что хотите удалить ключ?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard,
    )

    await callback.answer()


@router.callback_query(F.data == "wallet_remove_confirm")
async def callback_wallet_remove_confirm(callback: CallbackQuery):
    """Подтверждение удаления ключа."""
    # Проверка прав
    admin_ids = settings.get_admin_ids()
    if not admin_ids or callback.from_user.id != admin_ids[0]:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    try:
        # Путь к .env файлу
        env_file = "/opt/sigmatradebot/.env"

        # Читаем текущий .env
        with open(env_file) as f:
            env_lines = f.readlines()

        # Заменяем ключ на тестовый
        test_key = "0" * 64
        new_lines = []

        for line in env_lines:
            if line.startswith("wallet_private_key="):
                new_lines.append(f"wallet_private_key={test_key}\n")
            else:
                new_lines.append(line)

        # Записываем обновлённый .env
        with open(env_file, "w") as f:
            f.writelines(new_lines)

        await callback.message.edit_text(
            "✅ <b>Приватный ключ успешно удалён!</b>\n\n"
            "🔄 Перезапускаю бота для применения изменений...\n\n"
            "⚠️ Не забудьте установить новый ключ для работы с blockchain!",
            parse_mode="HTML",
        )

        # Перезапускаем Docker контейнеры
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "/opt/sigmatradebot/docker-compose.python.yml",
                "restart",
                "bot",
                "worker",
                "scheduler",
            ],
            check=True,
            capture_output=True,
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении:</b>\n{str(e)}\n\n"
            "Обратитесь к администратору сервера",
            parse_mode="HTML",
            reply_markup=get_wallet_management_keyboard(),
        )

    await callback.answer()


@router.callback_query(F.data == "wallet_close")
async def callback_wallet_close(callback: CallbackQuery):
    """Закрыть меню управления кошельком."""
    await callback.message.delete()
    await callback.answer("Меню закрыто")


# ============================================
# ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ДЛЯ БЫСТРОГО ДОСТУПА
# ============================================


@router.message(Command("wallet_status"))
async def cmd_wallet_status(message: Message):
    """
    Быстрый доступ к статусу кошелька.
    """
    # Проверка что пользователь - super admin
    admin_ids = settings.get_admin_ids()
    if not admin_ids or message.from_user.id != admin_ids[0]:
        await message.answer("❌ Команда доступна только super admin")
        return

    # Показываем статус
    current_key = settings.wallet_private_key
    is_test_key = current_key == "0" * 64 or not current_key

    if is_test_key:
        status_emoji = "🔴"
        status_text = "Тестовый ключ"
        warning = "\n\n⚠️ Установите реальный ключ через /wallet_menu"
    else:
        try:
            account = Account.from_key(settings.wallet_private_key)
            actual_address = account.address

            if actual_address.lower() == settings.wallet_address.lower():
                status_emoji = "🟢"
                status_text = "Ключ установлен и валиден"
                warning = ""
            else:
                status_emoji = "⚠️"
                status_text = "Ключ установлен, но адреса не совпадают"
                warning = (
                    f"\n\nФактический адрес: <code>{actual_address}</code>"
                )
        except Exception as e:
            status_emoji = "🔴"
            status_text = f"Ошибка ключа: {str(e)}"
            warning = "\n\n⚠️ Установите корректный ключ через /wallet_menu"

    await message.answer(
        f"{status_emoji} <b>СТАТУС КОШЕЛЬКА</b>\n\n"
        f"<b>Статус:</b> {status_text}\n"
        f"<b>Адрес:</b> <code>{settings.wallet_address}</code>{warning}\n\n"
        f"💡 Полное управление: /wallet_menu",
        parse_mode="HTML",
    )
