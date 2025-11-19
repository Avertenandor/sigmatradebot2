# ROI Система - Руководство для Администраторов

## 🎯 Обзор системы

ROI (Return on Investment) система ограничивает доход пользователей с депозитов уровня 1 до **500%** (5x).

## 🔧 Основные возможности администратора

### 1. Управление открытыми уровнями

**Панель админа** → **"⚙️ Депозиты"**

По умолчанию открыт только **Уровень 1 (10 USDT)**.

Вы можете открыть дополнительные уровни:
- Уровень 2 (50 USDT)
- Уровень 3 (100 USDT)
- Уровень 4 (500 USDT)
- Уровень 5 (1000 USDT)

**Важно**: Настройки кэшируются на 60 секунд для производительности.

### 2. Просмотр ROI статистики

**Панель админа** → **"⚙️ Депозиты"** → **"📊 ROI Статистика"**

Показывает:
```
📊 ROI Статистика (Уровень 1)

Общая информация:
🔄 Активных депозитов: 15
✅ Завершённых циклов: 8
💰 Всего внесено L1: 230.00 USDT
💸 Всего выплачено ROI: 187.50 USDT
📈 Средний прогресс: 62.3%

🔥 Близки к завершению (>80%):
1. User 123456789
   📊 94.2% | ⏳ 2.90 USDT
2. User 987654321
   📊 87.5% | ⏳ 6.25 USDT
```

## 📋 Бизнес-логика

### Правила системы

1. **Один активный L1 на пользователя**
   - Уникальный индекс в БД: `uq_active_level1_deposit_per_user`
   - Предотвращает создание дубликатов

2. **ROI Cap = 5x депозита**
   - Для L1 (10 USDT): максимум 50 USDT дохода
   - Инициализируется при подтверждении депозита

3. **Отслеживание прогресса**
   - `roi_paid_amount` увеличивается после каждой выплаты
   - `is_roi_completed = true` когда достигнут cap

4. **Автоматическое завершение**
   - При достижении 500% пользователь получает уведомление
   - Дальнейшие reward sessions не начисляют доход

## 🗄️ Структура БД

### Таблица `deposits`

Новые колонки:
```sql
roi_cap_amount      DECIMAL(20,8)  -- Максимум (5x для L1)
roi_paid_amount     DECIMAL(20,8)  -- Уже выплачено
is_roi_completed    BOOLEAN        -- Флаг завершения
roi_completed_at    TIMESTAMP      -- Дата завершения
```

Индексы:
```sql
-- Только один активный L1 на пользователя
CREATE UNIQUE INDEX uq_active_level1_deposit_per_user
ON deposits(user_id)
WHERE level = 1 AND status = 'confirmed' AND is_roi_completed = false;

-- Быстрый поиск завершённых
CREATE INDEX idx_deposits_roi_completed
ON deposits(is_roi_completed);
```

### Таблица `system_settings`

```sql
key: 'DEPOSITS_MAX_OPEN_LEVEL'
value: '1'  -- По умолчанию только L1
updated_at: TIMESTAMP
```

## 🔄 Как работает система

### 1. Создание депозита

```typescript
// DepositService.createPendingDeposit()
if (level === 1) {
  const activeL1 = await getActiveLevel1Cycle(userId);
  if (activeL1) {
    return { error: 'У вас уже есть активный депозит' };
  }
}
```

### 2. Подтверждение депозита

```typescript
// DepositService.confirmDeposit()
if (deposit.level === 1) {
  deposit.roi_cap_amount = depositAmount * 5;
  deposit.roi_paid_amount = '0';
  deposit.is_roi_completed = false;
}
```

### 3. Расчёт наград

```typescript
// RewardService.calculateRewardsForSession()
if (deposit.level === 1 && deposit.roi_cap_amount) {
  if (deposit.is_roi_completed) {
    continue; // Skip this deposit
  }

  const remaining = roiCap - roiPaid;
  if (rewardAmount > remaining) {
    rewardAmount = remaining; // Cap to remaining
  }
}
```

### 4. Выплата наград

```typescript
// PaymentService.processUserRewardPayments()
// Update ROI progress
deposit.roi_paid_amount += rewardAmount;

if (deposit.roi_paid_amount >= deposit.roi_cap_amount) {
  deposit.is_roi_completed = true;
  deposit.roi_completed_at = new Date();

  // Send notification
  await notificationService.notifyRoiCompleted();
}
```

## 📊 Мониторинг

### Ключевые метрики

1. **Активные циклы** (`totalActiveL1Deposits`)
   - Сколько пользователей сейчас зарабатывают

2. **Завершённые циклы** (`totalCompletedL1Cycles`)
   - Сколько циклов уже достигли 500%

3. **Средний прогресс** (`averageRoiProgress`)
   - В среднем сколько % ROI достигнуто

4. **Близкие к завершению** (`nearingCompletion`)
   - Пользователи с >80% ROI

### SQL запросы для мониторинга

```sql
-- Активные L1 депозиты
SELECT
  COUNT(*) as active_deposits,
  AVG((CAST(roi_paid_amount AS DECIMAL) / CAST(roi_cap_amount AS DECIMAL)) * 100) as avg_progress
FROM deposits
WHERE level = 1
  AND status = 'confirmed'
  AND is_roi_completed = false
  AND roi_cap_amount IS NOT NULL;

-- Завершённые циклы
SELECT COUNT(*) as completed_cycles
FROM deposits
WHERE level = 1
  AND is_roi_completed = true;

-- Близкие к завершению (>80%)
SELECT
  u.telegram_id,
  d.roi_paid_amount,
  d.roi_cap_amount,
  (CAST(d.roi_paid_amount AS DECIMAL) / CAST(d.roi_cap_amount AS DECIMAL) * 100) as progress_percent
FROM deposits d
JOIN users u ON d.user_id = u.id
WHERE d.level = 1
  AND d.is_roi_completed = false
  AND d.roi_cap_amount IS NOT NULL
  AND (CAST(d.roi_paid_amount AS DECIMAL) / CAST(d.roi_cap_amount AS DECIMAL)) > 0.8
ORDER BY progress_percent DESC;
```

## 🚨 Потенциальные проблемы

### 1. Дублирование L1 депозитов
**Предотвращение**: Уникальный индекс в БД
```sql
ERROR: duplicate key value violates unique constraint
       "uq_active_level1_deposit_per_user"
```

### 2. ROI превышает cap
**Предотвращение**:
- Проверка в `RewardService`
- Проверка в `PaymentService`

### 3. Кэш настроек устарел
**Решение**: TTL 60 секунд, автоматически обновляется

## 🔧 Настройка и обслуживание

### Изменение макс. открытого уровня

```typescript
// Через админ панель
await settingsService.setMaxOpenLevel(3); // Открыть L1-L3

// Напрямую в БД (не рекомендуется)
UPDATE system_settings
SET value = '3', updated_at = NOW()
WHERE key = 'DEPOSITS_MAX_OPEN_LEVEL';
```

### Ручная коррекция ROI

```sql
-- Посмотреть текущий прогресс
SELECT
  id,
  user_id,
  amount,
  roi_cap_amount,
  roi_paid_amount,
  is_roi_completed
FROM deposits
WHERE level = 1 AND user_id = <user_id>;

-- Скорректировать ROI (осторожно!)
UPDATE deposits
SET
  roi_paid_amount = '45.50',
  is_roi_completed = false
WHERE id = <deposit_id>;
```

## 📈 Будущие улучшения

Возможные расширения:
- [ ] ROI система для уровней 2-5
- [ ] Настраиваемый процент ROI (не только 500%)
- [ ] Автоматические бонусы при завершении цикла
- [ ] История всех завершённых циклов пользователя

## 🆘 Troubleshooting

### Пользователь жалуется что не может создать L1
1. Проверьте есть ли активный L1:
```sql
SELECT * FROM deposits
WHERE user_id = <user_id>
  AND level = 1
  AND status = 'confirmed'
  AND is_roi_completed = false;
```

2. Если есть, покажите прогресс ROI

### ROI не обновляется после payment
1. Проверьте логи `PaymentService.processUserRewardPayments`
2. Убедитесь что `roi_cap_amount` установлен:
```sql
SELECT * FROM deposits WHERE level = 1 AND roi_cap_amount IS NULL;
```

---

**Дата обновления**: 2025-01-12
**Версия системы**: ROI Part 2
**Ответственный**: Development Team
