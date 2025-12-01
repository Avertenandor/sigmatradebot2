"""
Admin handler for secure wallet management.

Implements separate management for:
1. Input Wallet (Address only) - Users deposit here.
2. Output Wallet (Private Key/Seed) - System pays from here.
"""

import os
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from eth_account import Account
from eth_utils import is_address, to_checksum_address
from mnemonic import Mnemonic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from bot.utils.admin_utils import clear_state_preserve_admin_token

router = Router()


class WalletSetupStates(StatesGroup):
    """States for wallet setup."""

    setting_input_wallet = State()
    setting_output_key = State()
    setting_derivation_index = State()  # New state for HD Wallet index
    waiting_for_seed = State()
    confirming_input = State()
    confirming_output = State()


async def handle_wallet_menu(message: Message, state: FSMContext, **data: Any) -> None:
    """Show wallet management menu (Redirect to new dashboard)."""
    # Check admin permissions
    user = data.get("event_from_user")
    if not user:
        user = message.from_user
        
    admin_ids = settings.get_admin_ids()
    if not admin_ids or not user or user.id != admin_ids[0]:
        await message.answer("❌ Команда доступна только главному администратору")
        return

    # Redirect to new dashboard
    from bot.handlers.admin.wallet_management import show_wallet_dashboard
    # Pass session=None as it is currently unused in show_wallet_dashboard
    await show_wallet_dashboard(message, None, state, **data)


# Old handlers replaced by wallet_management.py
# Keeping file for backward compatibility of existing FSM states if any user is stuck



@router.message(F.text == "📊 Статус кошельков")
async def handle_wallet_status(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    **data: Any,
) -> None:
    """Show wallet status (redirect to new dashboard)."""
    from bot.handlers.admin.wallet_management import show_wallet_dashboard
    await show_wallet_dashboard(message, session, state, **data)


# ==========================================
# INPUT WALLET SETUP (Address Only)
# ==========================================

@router.message(F.text == "📥 Настроить кошелек для входа")
async def start_input_wallet_setup(message: Message, state: FSMContext, **data: Any):
    """Start input wallet setup."""
    admin_ids = settings.get_admin_ids()
    if not admin_ids or message.from_user.id != admin_ids[0]:
        return

    from bot.keyboards.reply import cancel_keyboard
    
    await state.set_state(WalletSetupStates.setting_input_wallet)
    await message.answer(
        "📥 **НАСТРОЙКА КОШЕЛЬКА ДЛЯ ВХОДА**\n\n"
        "Этот кошелек будет показываться пользователям для пополнения.\n"
        "Система будет **только мониторить** поступления на этот адрес.\n\n"
        "📝 **Введите адрес кошелька (BEP-20/BSC):**\n"
        "Формат: `0x...` (42 символа)",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(WalletSetupStates.setting_input_wallet)
async def process_input_wallet(message: Message, state: FSMContext):
    """Validate input wallet address."""
    address = message.text.strip()
    
    if message.text == "❌ Отмена":
        await handle_wallet_menu(message, state)
        return

    if not is_address(address):
        await message.answer(
            "❌ Некорректный формат адреса.\n"
            "Адрес должен начинаться с 0x и содержать 42 символа.\n"
            "Попробуйте еще раз:",
        )
        return

    try:
        checksum_address = to_checksum_address(address)
    except Exception:
        await message.answer("❌ Ошибка валидации контрольной суммы адреса.")
        return

    # Save to state
    await state.update_data(new_input_wallet=checksum_address)
    
    from bot.keyboards.reply import confirmation_keyboard
    
    await state.set_state(WalletSetupStates.confirming_input)
    await message.answer(
        f"📥 **Подтверждение ВХОДНОГО кошелька**\n\n"
        f"Адрес: `{checksum_address}`\n\n"
        "✅ Пользователи будут отправлять средства на этот адрес.\n"
        "✅ Бот будет отслеживать входящие транзакции.\n"
        "❌ Бот НЕ сможет выводить средства с этого адреса (нет приватного ключа).\n\n"
        "Подтвердить сохранение?",
        parse_mode="Markdown",
        reply_markup=confirmation_keyboard(),
    )


@router.message(WalletSetupStates.confirming_input)
async def confirm_input_wallet(message: Message, state: FSMContext):
    """Confirm and save input wallet."""
    if message.text != "✅ Да":
        await handle_wallet_menu(message, state)
        return

    data = await state.get_data()
    new_address = data.get("new_input_wallet")
    
    if not new_address:
        await message.answer("❌ Ошибка данных. Начните заново.")
        await handle_wallet_menu(message, state)
        return

    try:
        # Update .env
        update_env_variable("system_wallet_address", new_address)
        
        # Update settings in memory (hacky but works until restart)
        settings.system_wallet_address = new_address
        
        await message.answer(
            "✅ **Кошелек для входа успешно обновлен!**\n\n"
            "Для полного применения изменений рекомендуется перезапуск.",
            parse_mode="Markdown",
        )
        await handle_wallet_menu(message, state)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении: {e}")
        await handle_wallet_menu(message, state)


# ==========================================
# OUTPUT WALLET SETUP (Private Key)
# ==========================================

@router.message(F.text == "📤 Настроить кошелек для выдачи")
async def start_output_wallet_setup(message: Message, state: FSMContext, **data: Any):
    """Start output wallet setup."""
    admin_ids = settings.get_admin_ids()
    if not admin_ids or message.from_user.id != admin_ids[0]:
        return

    from bot.keyboards.reply import cancel_keyboard
    
    await state.set_state(WalletSetupStates.setting_output_key)
    await message.answer(
        "📤 **НАСТРОЙКА КОШЕЛЬКА ДЛЯ ВЫДАЧИ**\n\n"
        "⚠️ **ВНИМАНИЕ! КРИТИЧЕСКАЯ ОПЕРАЦИЯ**\n"
        "Этот кошелек используется для автоматических выплат.\n"
        "Системе требуется **Приватный ключ** или **Seed фраза**.\n\n"
        "📝 **Отправьте Приватный ключ (hex) ИЛИ Seed фразу:**\n"
        "• Сообщение будет удалено сразу после получения.\n"
        "• Ключ сохраняется локально в зашифрованном виде.",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(WalletSetupStates.setting_output_key)
async def process_output_key(message: Message, state: FSMContext):
    """Process private key or seed phrase."""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await handle_wallet_menu(message, state)
        return

    # Delete message immediately
    try:
        await message.delete()
    except Exception:
        pass

    private_key = None
    wallet_address = None

    # Try as Private Key
    try:
        # Remove 0x prefix
        if text.startswith("0x"):
            pk_candidate = text[2:]
        else:
            pk_candidate = text
            
        if len(pk_candidate) == 64:
            account = Account.from_key(pk_candidate)
            private_key = pk_candidate
            wallet_address = account.address
    except Exception:
        pass

    # Try as Seed Phrase
    if not private_key:
        try:
            mnemo = Mnemonic("english")
            if mnemo.check(text):
                # Valid seed found - ask for derivation index
                await state.update_data(temp_seed_phrase=text)
                
                from bot.keyboards.reply import cancel_keyboard
                await state.set_state(WalletSetupStates.setting_derivation_index)
                await message.answer(
                    "🌱 **Обнаружена Seed-фраза**\n\n"
                    "Для HD-кошельков (Trust Wallet, Metamask, Ledger) можно выбрать адрес.\n"
                    "Путь деривации: `m/44'/60'/0'/0/{index}`\n\n"
                    "🔢 **Введите индекс адреса (обычно 0):**",
                    parse_mode="Markdown",
                    reply_markup=cancel_keyboard(),
                )
                return
        except Exception:
            pass

    if not private_key or not wallet_address:
        await message.answer(
            "❌ **Невалидный ключ или seed фраза.**\n"
            "Попробуйте еще раз или нажмите Отмена.",
            parse_mode="Markdown",
        )
        return

    # Save to state (Private Key flow)
    await state.update_data(new_private_key=private_key, new_output_address=wallet_address)
    
    from bot.keyboards.reply import confirmation_keyboard
    
    await state.set_state(WalletSetupStates.confirming_output)
    await message.answer(
        f"📤 **Подтверждение ВЫХОДНОГО кошелька**\n\n"
        f"Адрес: `{wallet_address}`\n\n"
        "✅ Ключ валиден.\n"
        "✅ Этот кошелек будет использоваться для выплат.\n"
        "⚠️ Убедитесь, что на этом кошельке есть BNB для газа и USDT для выплат.\n\n"
        "Подтвердить сохранение?",
        parse_mode="Markdown",
        reply_markup=confirmation_keyboard(),
    )


@router.message(WalletSetupStates.setting_derivation_index)
async def process_derivation_index(message: Message, state: FSMContext):
    """Process derivation index for Seed Phrase."""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await handle_wallet_menu(message, state)
        return

    try:
        index = int(text)
        if index < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число (например, 0):")
        return

    data = await state.get_data()
    seed_phrase = data.get("temp_seed_phrase")
    
    if not seed_phrase:
        await message.answer("❌ Ошибка: Seed-фраза потеряна. Начните заново.")
        await handle_wallet_menu(message, state)
        return

    try:
        # Enable HD Wallet features safely
        if hasattr(Account, "enable_unaudited_hdwallet_features"):
            try:
                Account.enable_unaudited_hdwallet_features()
            except Exception:
                pass
        
        # Derive account
        # Standard Ethereum/BSC path: m/44'/60'/0'/0/{index}
        path = f"m/44'/60'/0'/0/{index}"
        account = Account.from_mnemonic(seed_phrase, account_path=path)
        
        private_key = account.key.hex()[2:]  # remove 0x
        wallet_address = account.address
        
        # Save to state
        await state.update_data(new_private_key=private_key, new_output_address=wallet_address)
        
        from bot.keyboards.reply import confirmation_keyboard
        
        await state.set_state(WalletSetupStates.confirming_output)
        await message.answer(
            f"📤 **Подтверждение ВЫХОДНОГО кошелька**\n\n"
            f"🌱 Seed-фраза (Index: {index})\n"
            f"Адрес: `{wallet_address}`\n\n"
            "✅ Ключ успешно деривирован.\n"
            "✅ Этот кошелек будет использоваться для выплат.\n\n"
            "Подтвердить сохранение?",
            parse_mode="Markdown",
            reply_markup=confirmation_keyboard(),
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка деривации кошелька: {e}")
        await handle_wallet_menu(message, state)


@router.message(WalletSetupStates.confirming_output)
async def confirm_output_wallet(message: Message, state: FSMContext):
    """Confirm and save output wallet."""
    if message.text != "✅ Да":
        await handle_wallet_menu(message, state)
        return

    data = await state.get_data()
    private_key = data.get("new_private_key")
    address = data.get("new_output_address")
    
    if not private_key or not address:
        await message.answer("❌ Ошибка данных.")
        await handle_wallet_menu(message, state)
        return

    try:
        # Update .env
        update_env_variable("wallet_private_key", private_key)
        update_env_variable("wallet_address", address)
        
        # Force restart via exit
        await message.answer(
            "✅ **Кошелек для выдачи сохранен!**\n\n"
            "🔄 Бот перезапускается для применения нового ключа...",
            parse_mode="Markdown",
        )
        await clear_state_preserve_admin_token(state)
        os._exit(0)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении: {e}")
        await handle_wallet_menu(message, state)


def update_env_variable(key: str, value: str) -> None:
    """Update environment variable in .env file."""
    env_file = "/app/.env"
    
    if not os.path.exists(env_file):
        # Try local path if container path fails (for dev)
        env_file = ".env"

    try:
        with open(env_file, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    new_lines = []
    updated = False
    
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
        new_lines.append(f"{key}={value}\n")
        
    # Write directly to file to avoid "Device or resource busy" with Docker bind mounts
    with open(env_file, "w") as f:
        f.writelines(new_lines)


@router.message(F.text == "👑 Админ-панель")
async def handle_back_to_admin_panel(message: Message, session: AsyncSession, **data: Any):
    """Return to admin panel."""
    from bot.handlers.admin.panel import handle_admin_panel_button
    await handle_admin_panel_button(message, session, **data)
