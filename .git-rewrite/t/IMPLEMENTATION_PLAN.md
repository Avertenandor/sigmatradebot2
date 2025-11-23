# План реализации SigmaTrade Bot

## Фаза 1: Фундамент (Текущая фаза)

### ✅ Завершено
- [x] Архитектурный план
- [x] Структура проекта
- [x] Docker конфигурация
- [x] Скрипты deployment и backup

### 🔄 В процессе
- [ ] Константы и утилиты
- [ ] Конфигурационные модули
- [ ] Database entities (TypeORM)
- [ ] Database migrations

## Фаза 2: Database & Core (2-3 дня)

### Entities (TypeORM)
```typescript
✓ User.entity.ts - Пользователи
✓ Wallet.entity.ts - Кошельки (если нужно отдельно)
✓ Deposit.entity.ts - Депозиты
✓ Transaction.entity.ts - Транзакции
✓ Referral.entity.ts - Реферальные связи
✓ ReferralEarning.entity.ts - Реферальные доходы
✓ Admin.entity.ts - Администраторы
✓ UserAction.entity.ts - Действия пользователей (TTL 7 дней)
```

### Repositories
```typescript
✓ UserRepository - CRUD + поиск по telegram_id, wallet
✓ DepositRepository - Проверка уровней, история
✓ ReferralRepository - Построение цепочки рефералов
✓ TransactionRepository - История транзакций
```

## Фаза 3: Telegram Bot Core (3-4 дня)

### Handlers
```typescript
✓ start.handler.ts - Приветствие + глубокие ссылки (referral)
✓ registration.handler.ts - Регистрация с BSC адресом
✓ verification.handler.ts - Генерация финансового пароля
✓ profile.handler.ts - Профиль пользователя
✓ help.handler.ts - Помощь
```

### Keyboards
```typescript
✓ main.keyboard.ts - Главное меню
✓ navigation.keyboard.ts - Кнопка "Назад"
✓ registration.keyboard.ts - Процесс регистрации
```

### Middlewares
```typescript
✓ auth.middleware.ts - Проверка регистрации
✓ ban.middleware.ts - Проверка бана
✓ rateLimit.middleware.ts - Rate limiting
✓ logger.middleware.ts - Логирование действий
```

## Фаза 4: Депозитная система (3-4 дня)

### Handlers
```typescript
✓ deposit.handler.ts - Выбор уровня депозита
✓ depositInfo.handler.ts - Информация о депозите
✓ depositHistory.handler.ts - История депозитов
```

### Services
```typescript
✓ deposit.service.ts
  - checkDepositEligibility() - Проверка возможности активации
  - getAvailableDepositLevels() - Доступные уровни
  - calculateRequiredReferrals() - Требуемые рефералы
  - getDepositHistory() - История
```

### Keyboards
```typescript
✓ deposit.keyboard.ts - Выбор уровня (10/50/100/150/300 USDT)
```

## Фаза 5: Реферальная система (2-3 дня)

### Handlers
```typescript
✓ referral.handler.ts - Реферальная ссылка
✓ referralStats.handler.ts - Статистика рефералов
✓ referralEarnings.handler.ts - Доходы
```

### Services
```typescript
✓ referral.service.ts
  - generateReferralLink() - Генерация ссылки
  - getReferralChain(userId, depth) - Цепочка до 3 уровней
  - countDirectReferrals() - Прямые рефералы
  - calculateReferralReward() - Расчет вознаграждения
  - getReferralStats() - Статистика
```

## Фаза 6: Blockchain Integration (4-5 дней)

### Blockchain Services
```typescript
✓ monitor.service.ts
  - startBlockMonitoring() - Начать мониторинг WebSocket
  - processBlock(block) - Обработка блока
  - detectDeposit(tx) - Детект депозита
  - verifyTransaction(txHash) - Верификация

✓ wallet.service.ts
  - getBalance(address) - Баланс
  - sendUSDT(to, amount) - Отправка USDT
  - estimateGas() - Оценка газа

✓ usdt.contract.ts
  - Interface для USDT BEP-20
  - Transfer events parsing
```

### Payment Processor
```typescript
✓ payment.service.ts
  - processReferralPayouts() - Обработка выплат
  - queuePayment() - Добавить в очередь
  - executePayment() - Выполнить выплату
```

## Фаза 7: Admin Panel (2-3 дня)

### Handlers
```typescript
✓ admin.handler.ts
  - /admin - Вход в админку
  - broadcastMessage() - Рассылка всем
  - sendToUser() - Отправка одному
  - banUser() - Бан пользователя
  - unbanUser() - Разбан
  - promoteAdmin() - Назначить админа
  - getStats() - Статистика платформы
```

### Keyboards
```typescript
✓ admin.keyboard.ts
  - Рассылка
  - Отправить пользователю
  - Управление банами
  - Назначить админа
  - Статистика
  - Назад
```

### Middlewares
```typescript
✓ admin.middleware.ts - Проверка прав админа
```

## Фаза 8: Background Jobs (2-3 дня)

### Jobs (Bull Queue)
```typescript
✓ blockchain-monitor.job.ts
  - Непрерывный мониторинг блокчейна
  - Обработка новых блоков

✓ payment-processor.job.ts
  - Обработка очереди выплат
  - Реферальные вознаграждения

✓ referral-calculator.job.ts
  - Расчет реферальных наград
  - Начисление по 3 уровням

✓ backup.job.ts
  - Ежедневный бэкап БД (cron: 0 4 * * *)
  - Commit в git
  - Upload в GCS

✓ log-cleanup.job.ts
  - Еженедельная очистка (cron: 0 3 * * 0)
  - Удаление UserActions старше 7 дней
```

## Фаза 9: Security & Protection (2-3 дня)

### Rate Limiting
```typescript
✓ Redis-based rate limiter
✓ Per-user limits (30 req/min)
✓ Per-IP limits (100 req/min)
✓ Endpoint-specific limits
```

### Validation
```typescript
✓ Joi schemas для всех input
✓ BSC address validation
✓ Financial password strength
✓ Sanitization
```

### DDoS Protection
```typescript
✓ nginx rate limiting
✓ Connection limits
✓ Request timeouts
✓ Payload size limits
```

## Фаза 10: Testing (3-4 дня)

### Unit Tests
```typescript
✓ Services (deposit, referral, payment)
✓ Utilities (validation, crypto)
✓ Blockchain services (mocked)
```

### Integration Tests
```typescript
✓ Database operations
✓ Redis operations
✓ Bot flow integration
```

### E2E Tests
```typescript
✓ Full user registration flow
✓ Deposit activation flow
✓ Referral flow
✓ Admin operations
```

## Фаза 11: Deployment (2-3 дня)

### GCP Setup
```bash
✓ Create GCP project
✓ Setup Cloud SQL (PostgreSQL)
✓ Setup Memorystore (Redis)
✓ Create Compute Engine VM
✓ Configure Cloud Armor (DDoS)
✓ Setup Cloud Storage (backups)
✓ Configure Secret Manager
```

### CI/CD Pipeline
```yaml
✓ GitHub Actions workflow
✓ Automated testing
✓ Docker build & push
✓ Deployment automation
```

### Monitoring
```typescript
✓ Cloud Monitoring dashboards
✓ Alerting rules
✓ Log aggregation
✓ Health checks
```

---

## Порядок разработки (Последовательность)

### Неделя 1-2: Foundation
1. ✅ Константы и конфиги
2. ✅ Утилиты (logger, validation, crypto)
3. ✅ Database entities
4. ✅ Migrations
5. ✅ Repositories

### Неделя 3: Bot Core
6. ✅ Базовая структура бота
7. ✅ Middlewares (auth, rate-limit)
8. ✅ Start handler + приветствие
9. ✅ Registration handler
10. ✅ Verification handler

### Неделя 4: Deposits
11. ✅ Deposit service
12. ✅ Deposit handlers
13. ✅ Level validation logic
14. ✅ Deposit keyboards

### Неделя 5: Referrals
15. ✅ Referral service
16. ✅ Referral handlers
17. ✅ Deep linking (реф. ссылки)
18. ✅ Referral stats

### Неделя 6-7: Blockchain
19. ✅ QuickNode integration
20. ✅ USDT contract interface
21. ✅ Block monitor
22. ✅ Transaction detector
23. ✅ Payment processor

### Неделя 8: Admin
24. ✅ Admin middleware
25. ✅ Admin handlers
26. ✅ Broadcast system
27. ✅ User management

### Неделя 9: Jobs & Polish
28. ✅ Background jobs setup
29. ✅ Backup automation
30. ✅ Log cleanup
31. ✅ Security hardening

### Неделя 10: Deploy & Test
32. ✅ GCP deployment
33. ✅ Production testing
34. ✅ Monitoring setup
35. ✅ Final adjustments

---

## Критические зависимости

### Перед началом разработки нужно:
- [x] Telegram Bot Token
- [x] QuickNode BSC endpoint (WSS + HTTPS)
- [x] Системный кошелек (прием депозитов)
- [x] Выплатной кошелек (рефералы)
- [x] GCP аккаунт

### Для деплоя нужно:
- [ ] Domain для бота (опционально)
- [ ] SSL сертификаты (Let's Encrypt)
- [ ] GCP проект настроен
- [ ] Приватный ключ выплатного кошелька в Secret Manager

---

## Текущий статус

**Фаза:** 1 - Фундамент
**Прогресс:** 30%
**Следующий шаг:** Создание констант, конфигов и утилит

---

## Заметки по реализации

### Важно реализовать:
1. **Атомарность операций** - Все депозиты и выплаты через transactions
2. **Идемпотентность** - Повторная обработка транзакций не должна дублировать записи
3. **Graceful shutdown** - Корректное завершение при остановке
4. **Circuit breaker** - Для blockchain запросов
5. **Exponential backoff** - При ошибках QuickNode

### Безопасность:
1. **Never commit** приватные ключи
2. **Always validate** user input
3. **Rate limit** все endpoints
4. **Log** все критичные операции
5. **Encrypt** sensitive data в БД

### Performance:
1. **Index** все foreign keys
2. **Cache** user data в Redis
3. **Batch** blockchain queries
4. **Optimize** N+1 queries
5. **Monitor** slow queries

---

**Начинаем разработку! 🚀**
