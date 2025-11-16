# 🔄 ПЛАН РЕФАКТОРИНГА: ЗАМЕНА INLINE НА REPLY KEYBOARDS

## 📋 ЦЕЛЬ
Убрать ВСЕ inline кнопки (под сообщениями) и оставить только reply keyboards (нижняя панель).

## ✅ ВЫПОЛНЕНО

### 1. Расширены Reply Keyboards (`bot/keyboards/reply.py`)
- ✅ `deposit_keyboard()` - меню депозитов (5 уровней)
- ✅ `withdrawal_keyboard()` - меню выводов
- ✅ `referral_keyboard()` - меню рефералов
- ✅ `settings_keyboard()` - меню настроек
- ✅ `admin_keyboard()` - админ-панель
- ✅ `admin_users_keyboard()` - управление пользователями
- ✅ `admin_withdrawals_keyboard()` - управление выводами
- ✅ `confirmation_keyboard()` - подтверждение (Да/Нет)
- ✅ `cancel_keyboard()` - отмена действия

### 2. Обновлены константы кнопок (`bot/utils/menu_buttons.py`)
- ✅ Добавлены все новые тексты кнопок
- ✅ Группированы по разделам (Main, Deposit, Withdrawal, Referral, Settings, Support, Admin)
- ✅ Добавлены кнопки подтверждения

## 🔧 ТРЕБУЕТСЯ ВЫПОЛНИТЬ

### Этап 1: Обновить Menu Handler (`bot/handlers/menu.py`)

#### Текущие проблемы:
- ❌ Используются `@router.callback_query()` декораторы
- ❌ Используются inline keyboards из `bot/keyboards/inline.py`
- ❌ Функции принимают `Message | CallbackQuery`

#### Что исправить:
```python
# БЫЛО:
@router.message(F.text == "💰 Депозит")
@router.callback_query(F.data == "menu:deposit")
async def show_deposit_menu(event: Message | CallbackQuery, ...):
    # ... код с inline keyboard

# ДОЛЖНО БЫТЬ:
@router.message(F.text == "💰 Депозит")
async def show_deposit_menu(message: Message, ...):
    await message.answer(
        "Выберите уровень депозита:",
        reply_markup=deposit_keyboard()
    )
```

#### Функции для изменения в menu.py:
1. `show_main_menu()` - ✅ Уже использует reply keyboard
2. `show_balance()` - убрать callback_query
3. `show_history()` - убрать callback_query
4. `show_deposit_menu()` - убрать callback_query, использовать reply keyboard
5. `show_withdrawal_menu()` - убрать callback_query, использовать reply keyboard
6. `show_referral_menu()` - убрать callback_query, использовать reply keyboard
7. `show_support_menu()` - убрать callback_query, использовать reply keyboard
8. `show_settings_menu()` - убрать callback_query, использовать reply keyboard
9. `show_rewards_menu()` - убрать callback_query
10. `show_profile_settings()` - убрать callback_query
11. `show_wallet_settings()` - убрать callback_query
12. `show_notification_settings()` - убрать callback_query
13. `start_update_contacts()` - убрать callback_query

### Этап 2: Обновить Deposit Handler (`bot/handlers/deposit.py`)

#### Что исправить:
- Добавить handlers для новых кнопок:
  - "💰 Пополнить Level 1 (50 USDT)"
  - "💰 Пополнить Level 2 (100 USDT)"
  - "💰 Пополнить Level 3 (250 USDT)"
  - "💰 Пополнить Level 4 (500 USDT)"
  - "💰 Пополнить Level 5 (1000 USDT)"
- Убрать все `callback_query` handlers
- Заменить inline keyboards на reply keyboards

### Этап 3: Обновить Withdrawal Handler (`bot/handlers/withdrawal.py`)

#### Что исправить:
- Добавить handlers для новых кнопок:
  - "💸 Вывести всю сумму"
  - "💵 Вывести указанную сумму"
  - "📜 История выводов"
- Убрать все `callback_query` handlers
- Заменить inline keyboards на reply keyboards

### Этап 4: Обновить Referral Handler (`bot/handlers/referral.py`)

#### Что исправить:
- Добавить handlers для новых кнопок:
  - "👥 Мои рефералы"
  - "💰 Мой заработок"
  - "📊 Статистика рефералов"
- Убрать все `callback_query` handlers
- Заменить inline keyboards на reply keyboards

### Этап 5: Обновить Settings Handlers

#### Profile (`bot/handlers/profile.py`):
- Добавить handler для "👤 Мой профиль"
- Убрать callback_query handlers

#### Settings menu:
- Добавить handler для "💳 Мой кошелек"
- Добавить handler для "🔔 Настройки уведомлений"
- Добавить handler для "📝 Обновить контакты"

### Этап 6: Обновить Support Handler (`bot/handlers/support.py`)

#### Что исправить:
- Добавить handlers для новых кнопок:
  - "✉️ Создать обращение"
  - "📋 Мои обращения"
  - "❓ FAQ"
- Убрать все `callback_query` handlers
- Заменить inline keyboards на reply keyboards

### Этап 7: Обновить Admin Handlers

#### Admin Panel (`bot/handlers/admin/panel.py`):
- Добавить handlers для новых кнопок:
  - "👥 Управление пользователями"
  - "💸 Управление выводами"
  - "📊 Статистика бота"
  - "📢 Рассылка"
  - "⚙️ Настройки депозитов"
  - "🔑 Настройки кошелька"
  - "🚫 Управление blacklist"
- Убрать все `callback_query` handlers

#### Admin Users (`bot/handlers/admin/users.py`):
- Добавить handlers для:
  - "🔍 Найти пользователя"
  - "👥 Список пользователей"
  - "🚫 Заблокировать пользователя"
  - "⚠️ Терминировать аккаунт"

#### Admin Withdrawals (`bot/handlers/admin/withdrawals.py`):
- Добавить handlers для:
  - "⏳ Ожидающие выводы"
  - "✅ Одобренные выводы"
  - "❌ Отклоненные выводы"

### Этап 8: Универсальные изменения во всех handlers

Для КАЖДОГО handler файла нужно:

1. **Удалить импорты inline keyboards:**
```python
# Удалить:
from bot.keyboards.inline import (
    main_menu_keyboard,
    deposit_keyboard,
    # и т.д.
)
```

2. **Добавить импорты reply keyboards:**
```python
# Добавить:
from bot.keyboards.reply import (
    main_menu_reply_keyboard,
    deposit_keyboard,
    withdrawal_keyboard,
    # и т.д.
)
```

3. **Убрать декораторы `@router.callback_query()`:**
```python
# Удалить эти строки:
@router.callback_query(F.data == "menu:something")
```

4. **Изменить типы параметров:**
```python
# Было:
async def handler(event: Message | CallbackQuery, ...):

# Должно быть:
async def handler(message: Message, ...):
```

5. **Заменить отправку сообщений:**
```python
# Было:
if isinstance(event, CallbackQuery):
    await event.message.edit_text(...)
else:
    await event.answer(...)

# Должно быть:
await message.answer(...)
```

6. **Заменить inline keyboards на reply:**
```python
# Было:
await message.answer("Текст", reply_markup=some_inline_keyboard())

# Должно быть:
await message.answer("Текст", reply_markup=some_reply_keyboard())
```

### Этап 9: Добавить обработку "📊 Главное меню"

Во всех submenu handlers добавить обработчик возврата в главное меню:

```python
@router.message(F.text == "📊 Главное меню")
async def return_to_main_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Return to main menu from any submenu."""
    await state.clear()
    await show_main_menu(message, session, user, state)
```

### Этап 10: Удалить/Заархивировать inline.py

После завершения рефакторинга:
- Переименовать `bot/keyboards/inline.py` в `bot/keyboards/inline.py.deprecated`
- Или полностью удалить файл
- Убедиться что нигде не осталось импортов из него

## 📝 ПРОВЕРОЧНЫЙ СПИСОК

После завершения рефакторинга проверить:

- [ ] Нет импортов из `bot.keyboards.inline`
- [ ] Нет `@router.callback_query()` decorators
- [ ] Все handlers принимают только `Message` (не `Message | CallbackQuery`)
- [ ] Все клавиатуры - только `ReplyKeyboardMarkup`
- [ ] Все тексты кнопок есть в `menu_buttons.py`
- [ ] Кнопка "📊 Главное меню" работает из всех подменю
- [ ] Все FSM handlers проверяют `is_menu_button()`
- [ ] Бот работает только с reply keyboards внизу экрана

## 🔍 КОМАНДЫ ДЛЯ ПОИСКА ПРОБЛЕМНЫХ МЕСТ

```bash
# Найти все callback_query decorators
grep -r "@router.callback_query" bot/handlers/

# Найти все импорты inline keyboards
grep -r "from bot.keyboards.inline" bot/

# Найти все использования Message | CallbackQuery
grep -r "Message | CallbackQuery" bot/handlers/

# Найти все CallbackQuery
grep -r "CallbackQuery" bot/handlers/
```

## 📊 ПРОГРЕСС

- **Reply Keyboards созданы:** 100%
- **Menu buttons обновлены:** 100%
- **Handlers обновлены:** 0%
- **Тестирование:** 0%

**Общий прогресс:** ~20%

---

**Статус:** 🔄 В ПРОЦЕССЕ  
**Приоритет:** 🔥 ВЫСОКИЙ  
**Ответственный:** AI Assistant

