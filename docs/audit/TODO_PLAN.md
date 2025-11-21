# Детальный план TODO для доработки сценариев

**Дата создания:** 2025-01-24  
**Статус:** Готов к выполнению

---

## Критические пробелы (начать сразу)

### TODO-1: R1-3 - Добавить явную проверку blacklist в `/start`

**Приоритет:** Критический  
**Оценка:** 2 часа  
**Файл:** `bot/handlers/start.py`

**Задача:**
Добавить явную проверку blacklist для незарегистрированных пользователей в `cmd_start()` перед началом регистрации.

**Действия:**
1. В `cmd_start()` после строки 159 (перед показом приветствия для незарегистрированных):
   - Получить `blacklist_entry` из middleware data или запросить из БД
   - Проверить `blacklist_entry.action_type == BlacklistActionType.REGISTRATION_DENIED`
   - Если true → показать сообщение "Регистрация недоступна. Обратитесь в поддержку" и `return`
   - Не устанавливать FSM состояние `waiting_for_wallet`

**Код:**
```python
# После строки 159 в cmd_start()
# Check blacklist for non-registered users
blacklist_entry = data.get("blacklist_entry")
if blacklist_entry is None:
    from app.repositories.blacklist_repository import BlacklistRepository
    blacklist_repo = BlacklistRepository(session)
    blacklist_entry = await blacklist_repo.find_by_telegram_id(
        message.from_user.id
    )

if blacklist_entry and blacklist_entry.is_active:
    from app.models.blacklist import BlacklistActionType
    if blacklist_entry.action_type == BlacklistActionType.REGISTRATION_DENIED:
        await message.answer(
            "❌ Регистрация недоступна.\n\n"
            "Обратитесь в поддержку для получения дополнительной информации."
        )
        await state.clear()
        return
```

**Тесты:**
- `tests/e2e/test_registration_flow.py::test_start_blacklisted_user_registration_denied`

---

### TODO-2: R3-6 - Улучшить обработку ошибок депозитов

**Приоритет:** Критический  
**Оценка:** 4 часа  
**Файл:** `jobs/tasks/deposit_monitoring.py`

**Задача:**
Добавить поиск транзакции по истории блокчейна перед пометкой депозита как FAILED.

**Действия:**
1. В `_monitor_deposits_async()` перед пометкой как FAILED (строка 100):
   - Вызвать `blockchain_service.search_blockchain_for_deposit()` для поиска транзакции
   - Если найдена → подтвердить депозит
   - Если не найдена → пометить как EXPIRED_PENDING (новый статус) или FAILED
   - Уведомить пользователя с инструкциями

**Код:**
```python
# В _monitor_deposits_async() перед строкой 100
# R3-6: Last attempt to find transaction in blockchain history
found_tx = await blockchain_service.search_blockchain_for_deposit(
    user_wallet=deposit.user.wallet_address,
    expected_amount=deposit.amount,
    from_block=deposit.created_at_block or 0,
)
if found_tx:
    # Found transaction - confirm deposit
    await deposit_service.confirm_deposit(deposit.id, found_tx['block_number'])
    continue
```

**Тесты:**
- `tests/integration/test_deposit_monitoring.py::test_expired_deposit_recovery`

---

### TODO-3: R9-2 - Улучшить защиту от race condition при ROI и выводе

**Приоритет:** Критический  
**Оценка:** 6 часов  
**Файлы:** `app/services/withdrawal_service.py`, `app/services/reward_service.py`

**Задача:**
Добавить pessimistic locking и transaction isolation для предотвращения race conditions.

**Действия:**
1. В `WithdrawalService.request_withdrawal()`:
   - Использовать `SELECT ... FOR UPDATE NOWAIT` для блокировки пользователя
   - При конфликте → retry с задержкой 1-2 секунды
   - Использовать `REPEATABLE READ` isolation level

2. В `RewardService.calculate_rewards_for_session()`:
   - Использовать `SELECT ... FOR UPDATE` для блокировки депозитов
   - Использовать `REPEATABLE READ` isolation level

**Код:**
```python
# В withdrawal_service.py
async def request_withdrawal(...):
    async with self.session.begin():
        # Get user with lock
        user = await self.session.get(
            User, user_id, with_for_update=True, nowait=True
        )
        # ... rest of logic
```

**Тесты:**
- `tests/integration/test_withdrawal_race_conditions.py::test_roi_and_withdrawal_race`

---

### TODO-4: R10-3 - Улучшить защиту от компрометации админа

**Приоритет:** Критический  
**Оценка:** 8 часов  
**Файлы:** `app/services/admin_service.py`, `bot/handlers/admin/*`

**Задача:**
Добавить мониторинг подозрительных действий админа и автоматическую блокировку.

**Действия:**
1. Создать `app/services/admin_security_service.py`:
   - Мониторинг подозрительных действий (массовые баны, крупные выводы)
   - Автоматическая блокировка при превышении порогов
   - Уведомление super_admin

2. Добавить проверки в критических операциях:
   - Массовые баны
   - Одобрение крупных выводов
   - Изменение системных настроек

**Тесты:**
- `tests/security/test_admin_compromise_protection.py`

---

### TODO-5: R11-1, R11-2 - Улучшить обработку падений БД и Redis

**Приоритет:** Критический  
**Оценка:** 4 часа  
**Файлы:** `bot/middlewares/database_middleware.py`, `bot/middlewares/redis_middleware.py`

**Задача:**
Добавить graceful degradation при падении БД/Redis.

**Действия:**
1. В `DatabaseMiddleware`:
   - При `OperationalError` → показать сообщение "Временная недоступность, попробуйте позже"
   - Логировать критическую ошибку
   - Не падать с исключением

2. В `RedisMiddleware`:
   - При ошибке Redis → продолжить без кеширования
   - Логировать предупреждение
   - Не блокировать работу бота

**Тесты:**
- `tests/integration/test_database_failure.py`
- `tests/integration/test_redis_failure.py`

---

### TODO-6: R17-3 - Добавить emergency stop для выводов/депозитов

**Приоритет:** Критический  
**Оценка:** 4 часа  
**Файлы:** `app/config/settings.py`, `app/services/withdrawal_service.py`, `app/services/deposit_service.py`

**Задача:**
Добавить флаги emergency stop и проверки в сервисах.

**Действия:**
1. Добавить в `settings.py`:
   - `emergency_stop_withdrawals: bool = False`
   - `emergency_stop_deposits: bool = False`

2. В `WithdrawalService.request_withdrawal()`:
   - Проверить `settings.emergency_stop_withdrawals`
   - Если true → вернуть ошибку "Выводы временно приостановлены"

3. В `DepositService.create_deposit()`:
   - Проверить `settings.emergency_stop_deposits`
   - Если true → вернуть ошибку "Депозиты временно приостановлены"

**Тесты:**
- `tests/integration/test_emergency_stop.py`

---

## Высокие приоритеты

### TODO-7: R8-2 - Улучшить обработку заблокированного бота

**Приоритет:** Высокий  
**Оценка:** 3 часа  
**Файл:** `app/services/notification_service.py`

**Задача:**
Добавить обработку ошибки 403 "bot was blocked by the user".

**Действия:**
1. В `NotificationService.send_notification()`:
   - Перехватить `TelegramAPIError` с кодом 403
   - Установить `user.bot_blocked = True`
   - Установить `user.bot_blocked_at = NOW()`
   - Логировать событие

2. В `/start` handler:
   - Проверить `user.bot_blocked == True`
   - Сбросить флаг при успешном сообщении
   - Показать накопленные важные уведомления

**Тесты:**
- `tests/integration/test_bot_blocked_handling.py`

---

### TODO-8: R8-3 - Реализовать систему приоритетов уведомлений

**Приоритет:** Высокий  
**Оценка:** 6 часов  
**Файл:** `app/services/notification_service.py`

**Задача:**
Добавить Redis sorted set для очереди уведомлений с приоритетами.

**Действия:**
1. Создать `NotificationPriority` enum (P0, P1, P2, P3)
2. В `NotificationService.send_notification()`:
   - Добавить параметр `priority: NotificationPriority`
   - Добавить в Redis sorted set с score = priority.value * 1000 + timestamp
3. Создать worker `notification_dispatcher`:
   - Обрабатывать очередь по приоритету
   - Соблюдать rate limit 30 msg/sec

**Тесты:**
- `tests/integration/test_notification_priorities.py`

---

### TODO-9: R12-1 - Улучшить обработку timing edge cases

**Приоритет:** Высокий  
**Оценка:** 4 часа  
**Файлы:** `app/services/reward_service.py`, `app/services/withdrawal_service.py`

**Задача:**
Добавить обработку edge cases связанных с временем (переход через полночь, таймзоны).

**Действия:**
1. В `RewardService`:
   - Использовать UTC для всех временных операций
   - Проверять, что начисление происходит в правильный день

2. В `WithdrawalService`:
   - Учитывать таймзоны при проверке лимитов

**Тесты:**
- `tests/unit/test_timing_edge_cases.py`

---

### TODO-10: R13-2 - Улучшить защиту от button spam

**Приоритет:** Высокий  
**Оценка:** 3 часа  
**Файл:** `bot/middlewares/rate_limit_middleware.py`

**Задача:**
Добавить rate limiting для кнопок меню.

**Действия:**
1. В `RateLimitMiddleware`:
   - Добавить проверку для кнопок меню
   - Лимит: 10 нажатий в минуту
   - При превышении → показать "Слишком много действий, подождите"

**Тесты:**
- `tests/security/test_button_spam_protection.py`

---

### TODO-11: R14-3 - Реализовать log aggregation

**Приоритет:** Высокий  
**Оценка:** 8 часов  
**Файлы:** `app/services/log_aggregation_service.py` (новый)

**Задача:**
Создать сервис для агрегации и анализа логов.

**Действия:**
1. Создать `LogAggregationService`:
   - Агрегация ошибок по типам
   - Подсчет частоты ошибок
   - Алерты при превышении порогов

2. Интегрировать с существующим логированием

**Тесты:**
- `tests/integration/test_log_aggregation.py`

---

### TODO-12: R15-4, R15-5 - Улучшить обработку race conditions между ролями

**Приоритет:** Высокий  
**Оценка:** 6 часов  
**Файлы:** `app/services/blacklist_service.py`, `app/services/deposit_service.py`

**Задача:**
Добавить distributed locks для критических операций.

**Действия:**
1. В `BlacklistService.block_user_with_active_operations()`:
   - Использовать Redis lock перед блокировкой
   - Проверить активные операции под lock

2. В `DepositService.create_deposit()`:
   - Использовать Redis lock для предотвращения race conditions

**Тесты:**
- `tests/integration/test_role_race_conditions.py`

---

### TODO-13: R16-3 - Реализовать восстановление потерянного Telegram аккаунта

**Приоритет:** Высокий  
**Оценка:** 8 часов  
**Файлы:** `bot/handlers/account_recovery.py` (новый)

**Задача:**
Создать процесс восстановления доступа к аккаунту при потере Telegram.

**Действия:**
1. Создать FSM для восстановления:
   - Запрос wallet address
   - Проверка владения кошельком (signature)
   - Привязка нового telegram_id

2. Добавить в меню поддержки

**Тесты:**
- `tests/e2e/test_account_recovery.py`

---

### TODO-14: R16-4 - Улучшить обработку продажи аккаунта

**Приоритет:** Высокий  
**Оценка:** 4 часа  
**Файлы:** `app/services/fraud_detection_service.py`

**Задача:**
Добавить детекцию продажи аккаунта (смена telegram_id, быстрая смена кошелька).

**Действия:**
1. В `FraudDetectionService`:
   - Проверка частых смен telegram_id
   - Проверка быстрой смены кошелька
   - Повышение risk score

**Тесты:**
- `tests/security/test_account_selling_detection.py`

---

### TODO-15: R17-1, R17-2 - Реализовать версионирование депозитов

**Приоритет:** Высокий  
**Оценка:** 8 часов  
**Файлы:** `app/models/deposit_version.py` (новый), `app/services/deposit_service.py`

**Задача:**
Добавить версионирование условий депозитов и временное отключение уровней.

**Действия:**
1. Создать модель `DepositVersion`:
   - `level`, `amount`, `enabled`, `version`, `valid_from`, `valid_to`

2. В `DepositValidationService`:
   - Проверять актуальную версию условий
   - Проверять `enabled` флаг

**Тесты:**
- `tests/integration/test_deposit_versioning.py`

---

## Средние приоритеты

### TODO-16: R13-3 - Реализовать поддержку смены языка

**Приоритет:** Средний  
**Оценка:** 6 часов  
**Файлы:** `bot/handlers/language.py` (новый), `bot/i18n/` (новый)

**Задача:**
Добавить поддержку многоязычности.

**Действия:**
1. Создать структуру i18n:
   - `bot/i18n/ru.py`, `bot/i18n/en.py`
   - Хранить выбранный язык в `user.language`

2. Создать handler для смены языка

**Тесты:**
- `tests/e2e/test_language_change.py`

---

### TODO-17: R17-5 - Реализовать миграцию на новый smart contract

**Приоритет:** Средний  
**Оценка:** 12 часов  
**Файлы:** `app/services/contract_migration_service.py` (новый)

**Задача:**
Создать сервис для миграции на новый smart contract.

**Действия:**
1. Создать `ContractMigrationService`:
   - Версионирование контрактов
   - Миграция данных
   - Обратная совместимость

**Тесты:**
- `tests/integration/test_contract_migration.py`

---

### TODO-18: R18-1 - Улучшить защиту от dust attacks

**Приоритет:** Средний  
**Оценка:** 4 часа  
**Файлы:** `app/services/deposit_service.py`

**Задача:**
Добавить фильтрацию dust транзакций.

**Действия:**
1. В `DepositService`:
   - Проверять минимальную сумму депозита
   - Игнорировать транзакции меньше минимума

**Тесты:**
- `tests/security/test_dust_attack_protection.py`

---

## Тестирование (высокий приоритет)

### TODO-19: Создать тесты для всех сценариев R1-R18

**Приоритет:** Высокий  
**Оценка:** 40 часов  
**Файлы:** `tests/e2e/test_*.py`, `tests/integration/test_*.py`

**Задача:**
Создать полное покрытие тестами для всех 113 сценариев.

**Действия:**
1. Создать E2E тесты для пользовательских сценариев (R1-R5)
2. Создать интеграционные тесты для фоновых процессов (R7-R8)
3. Создать security тесты для безопасности (R9-R10, R18)
4. Создать тесты для админ-панели (R6)

**Структура:**
```
tests/
├── e2e/
│   ├── test_registration_flow.py
│   ├── test_user_flow.py
│   ├── test_investor_flow.py
│   ├── test_partner_flow.py
│   └── test_restricted_user_flow.py
├── integration/
│   ├── test_background_jobs.py
│   ├── test_notifications.py
│   └── test_race_conditions.py
└── security/
    ├── test_fraud_detection.py
    ├── test_admin_security.py
    └── test_threat_model.py
```

---

## Итоговая оценка трудозатрат

**Критические:** 6 задач × ~4 часа = 24 часа  
**Высокие:** 9 задач × ~6 часов = 54 часа  
**Средние:** 3 задачи × ~7 часов = 21 час  
**Тестирование:** 1 задача × 40 часов = 40 часов

**Всего:** ~139 часов (~17 рабочих дней)

---

**Следующий шаг:** Начать выполнение TODO-1 (R1-3)

