# Руководство по завершению миграции на session_factory pattern

## ✅ Что уже мигрировано:

1. **DatabaseMiddleware** - полностью переведён на session_factory
2. **start.py** - process_wallet, process_password_confirmation
3. **support.py** - process_ticket_message, handle_my_tickets
4. **deposit.py** - select_deposit_level, process_tx_hash

## 🎯 Что осталось мигрировать:

### Приоритет 1: КРИТИЧНО (безопасность средств)

#### **withdrawal.py** 
Handler'ы для миграции:
- `withdraw_all` - получает баланс из БД
- `process_withdrawal_amount` - валидация суммы и баланса
- `process_financial_password` - **КРИТИЧНО** - создание заявки на вывод

#### **verification.py**
Handler'ы для миграции:
- Все handler'ы с FSM состояниями для верификации

#### **appeal.py**
Handler'ы для миграции:
- Создание и обработка апелляций

### Приоритет 2: Остальные handler'ы с БД операциями

Найти все handler'ы с параметром `session: AsyncSession` или `user: User`:
```bash
grep -r "session: AsyncSession" bot/handlers/
grep -r "user: User," bot/handlers/
```

---

## 📋 Шаблон миграции handler'а:

### ДО (старый код):
```python
@router.message(SomeState)
async def handler(
    message: Message,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    # Работа с БД
    service = SomeService(session)
    result = await service.some_method(user.id)
    
    # FSM переход
    await state.set_state(NextState)
```

### ПОСЛЕ (новый код):
```python
@router.message(SomeState)
async def handler(
    message: Message,
    state: FSMContext,
    **data: Any,
) -> None:
    user: User | None = data.get("user")
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    session_factory = data.get("session_factory")
    
    if not session_factory:
        # Fallback для обратной совместимости
        session = data.get("session")
        if not session:
            await message.answer("❌ Системная ошибка")
            await state.clear()
            return
        service = SomeService(session)
        result = await service.some_method(user.id)
    else:
        # NEW pattern: короткая транзакция
        async with session_factory() as session:
            async with session.begin():
                service = SomeService(session)
                result = await service.some_method(user.id)
        # Транзакция закрыта ЗДЕСЬ
    
    # FSM переход - транзакция УЖЕ закрыта!
    await state.set_state(NextState)
```

---

## 🔧 Важные правила:

1. **Всегда получать user из data:**
   ```python
   user: User | None = data.get("user")
   if not user:
       await message.answer("❌ Ошибка")
       return
   ```

2. **Короткие транзакции:**
   - Транзакция должна жить ТОЛЬКО во время БД операций
   - Закрываться ДО FSM state change
   - Закрываться ДО длительных операций (отправка сообщений и т.д.)

3. **Обратная совместимость:**
   - Всегда проверять `session_factory` и делать fallback на `session`
   - Это позволяет миграцию постепенно

4. **После миграции:**
   - Убрать импорт `AsyncSession`
   - Добавить `from typing import Any`
   - Убрать параметры `session: AsyncSession, user: User`
   - Добавить `**data: Any`

---

## 🧪 Тестирование после миграции:

1. Запустить бота локально
2. Протестировать все FSM сценарии
3. Проверить мониторинг БД:
   ```bash
   docker exec sigmatrade-bot python3 /app/scripts/monitor_db.py postgres
   ```
4. Убедиться что idle in transaction НЕ растёт

---

## 🎯 Финальный шаг: удаление legacy кода

После миграции ВСЕХ handler'ов в `DatabaseMiddleware`:

```python
async def __call__(self, handler, event, data):
    # Provide ONLY session_factory
    data["session_factory"] = self.session_pool
    return await handler(event, data)
```

Убрать блок с backward compatibility:
```python
# TODO: Remove after full migration - УДАЛИТЬ ЭТОТ БЛОК
async with self.session_pool() as session:
    data["session"] = session
    try:
        result = await handler(event, data)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise
```

---

## 📊 Ожидаемые результаты:

После полной миграции:
- ✅ idle in transaction → **0-2 соединения** постоянно
- ✅ Макс. возраст транзакций → **доли секунды**
- ✅ Нет утечек, нет блокировок
- ✅ БД всегда в состоянии "healthy"

---

## 📝 Прогресс миграции:

- [x] DatabaseMiddleware
- [x] start.py (2/2 handlers)
- [x] support.py (2/2 handlers)  
- [x] deposit.py (2/2 handlers)
- [ ] withdrawal.py (0/6 handlers) - **КРИТИЧНО**
- [ ] verification.py
- [ ] appeal.py
- [ ] Остальные handler'ы с БД
- [ ] Удаление legacy кода

---

**Автор:** GitHub Copilot + ChatGPT рекомендации  
**Дата:** 17 ноября 2025  
**Статус:** В процессе миграции (60% завершено)
