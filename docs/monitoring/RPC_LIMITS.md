# RPC-лимиты и мониторинг

**Дата создания:** 2025-01-16  
**Статус:** Актуально  
**Версия:** 1.0

---

## Текущий план

### Провайдер: QuickNode

**Тариф:** $49/месяц  
**Сеть:** Binance Smart Chain (BSC)

**Лимиты:**
- **RPS (Requests Per Second):** 25 requests/second
- **Concurrent requests:** 10 одновременных запросов
- **Burst:** До 25 запросов в секунду (token bucket)

---

## Настройки в коде

### BlockchainService

**Файл:** `app/services/blockchain_service.py`

**Параметры:**
```python
BlockchainService(
    rpc_url=settings.quiknode_http_url,
    usdt_contract=settings.usdt_contract_address,
    wallet_private_key=settings.wallet_private_key,
    max_concurrent_rpc=10,  # Максимум одновременных запросов
    max_rps=25,              # Максимум запросов в секунду
)
```

### RPCRateLimiter

**Файл:** `app/services/blockchain/rpc_rate_limiter.py`

**Алгоритм:**
- **Semaphore:** Ограничивает количество одновременных запросов (10)
- **Token bucket:** Ограничивает RPS (25 токенов/секунду)
- **Stats tracking:** Отслеживает статистику использования

**Принцип работы:**
1. Запрос ждёт освобождения семафора (если уже 10 запросов)
2. Запрос ждёт токена в bucket (если RPS превышен)
3. После выполнения запроса токен возвращается в bucket

---

## Метрики /health endpoint

### Структура ответа

**URL:** `http://localhost:8080/health`

**Пример ответа:**
```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connection successful"
    },
    "blockchain": {
      "status": "healthy",
      "message": "Blockchain connection successful (Chain ID: 56)",
      "chain_id": 56,
      "rpc_stats": {
        "requests_last_minute": 45,
        "avg_response_time_ms": 120.5,
        "error_count": 0,
        "total_requests": 15234
      }
    }
  }
}
```

### Поля rpc_stats

| Поле | Тип | Описание |
|------|-----|----------|
| `requests_last_minute` | `int` | Количество RPC-запросов за последнюю минуту |
| `avg_response_time_ms` | `float` | Среднее время ответа в миллисекундах |
| `error_count` | `int` | Общее количество ошибок RPC (накопительное) |
| `total_requests` | `int` | Общее количество RPC-запросов (накопительное) |

---

## Пороги алертов

### WARN (Предупреждение)

**Условие:** `requests_last_minute > 1500`

**Расчёт:** 60% от плана = 25 RPS × 60 секунд × 0.6 = 1500 запросов/минуту

**Действие:**
- Логировать предупреждение
- Мониторить более внимательно
- Проверить, нет ли утечек в коде

### ALARM (Тревога)

**Условие:** `requests_last_minute > 1800`

**Расчёт:** 75% от плана = 25 RPS × 60 секунд × 0.75 = 1800 запросов/минуту

**Действие:**
- Отправить уведомление администратору
- Проверить логи на аномальную активность
- Рассмотреть оптимизацию запросов

### CRITICAL (Критично)

**Условие:** `error_count > 10` за последнюю минуту

**Действие:**
- Немедленно уведомить администратора
- Проверить доступность RPC-ноды
- Проверить логи на ошибки подключения

---

## Команды для проверки

### Health check

```bash
# Базовый health check
curl http://localhost:8080/health

# С форматированием JSON
curl -s http://localhost:8080/health | jq

# Только RPC-статистика
curl -s http://localhost:8080/health | jq '.checks.blockchain.rpc_stats'

# Только requests_last_minute
curl -s http://localhost:8080/health | jq '.checks.blockchain.rpc_stats.requests_last_minute'

# Проверка статуса блокчейна
curl -s http://localhost:8080/health | jq '.checks.blockchain.status'
```

### Логи RPC в реальном времени

```bash
# Логи RPC в реальном времени
docker compose -f docker-compose.python.yml logs -f bot | grep "\[RPC\]"

# Логи с фильтром по ошибкам
docker compose -f docker-compose.python.yml logs -f bot | grep -i "rpc.*error"

# Статистика RPC за последние 100 строк
docker compose -f docker-compose.python.yml logs --tail=100 bot | grep "\[RPC\]"
```

### Мониторинг на сервере

```bash
# SSH на сервер
gcloud compute ssh sigmatrade-20251108-210354 \
  --zone=europe-north1-a \
  --project=telegram-bot-444304

# Health check на сервере
curl -s http://localhost:8080/health | jq '.checks.blockchain.rpc_stats'

# Логи в реальном времени
docker compose -f docker-compose.python.yml logs -f bot | grep "\[RPC\]"
```

---

## Оптимизация использования RPC

### Батчинг запросов

**Принцип:** Объединять несколько запросов в один батч

**Примеры:**
1. **Event filters:** Загрузка всех событий `Transfer` за диапазон блоков одним запросом
2. **Multicall:** Объединение нескольких `eth_call` в один запрос (если поддерживается)

**Реализация:**
- `BlockchainService.monitor_incoming_deposits()` использует event filter
- Батчевая загрузка событий через `get_all_entries()`

### Кэширование

**Принцип:** Кэшировать результаты запросов, которые редко меняются

**Примеры:**
- Баланс кошелька (кэш на 30 секунд)
- Номер последнего блока (кэш на 5 секунд)
- Информация о транзакции (кэш навсегда после подтверждения)

### Оптимизация частоты проверок

**Принцип:** Не проверять статус транзакций слишком часто

**Примеры:**
- Pending депозиты: проверка раз в минуту (не каждый запрос)
- Статус транзакций: проверка только при необходимости

---

## Мониторинг в продакшене

### Ежедневная проверка

```bash
# Проверить RPC-статистику
curl -s http://localhost:8080/health | jq '.checks.blockchain.rpc_stats'

# Проверить, нет ли превышения лимитов
REQUESTS=$(curl -s http://localhost:8080/health | jq '.checks.blockchain.rpc_stats.requests_last_minute')
if [ "$REQUESTS" -gt 1500 ]; then
  echo "WARN: High RPC usage: $REQUESTS requests/minute"
fi
```

### Еженедельная проверка

1. Проверить общее количество запросов (`total_requests`)
2. Проверить количество ошибок (`error_count`)
3. Сравнить с предыдущей неделей
4. Выявить аномалии

### Дашборд QuickNode

**Рекомендация:** Настроить дашборд в QuickNode для визуализации:
- Requests per second (должно быть < 25)
- Error rate (должно быть < 1%)
- Response time (должно быть < 500ms)

---

## Troubleshooting

### Высокое использование RPC

**Симптомы:**
- `requests_last_minute > 1500`
- Медленные ответы от RPC

**Диагностика:**
1. Проверить логи: `docker compose logs bot | grep "\[RPC\]"`
2. Найти источники запросов (депозиты, выводы, мониторинг)
3. Проверить, нет ли утечек (запросы в циклах без лимитов)

**Решение:**
- Оптимизировать батчинг
- Увеличить интервалы проверок
- Добавить кэширование

### Ошибки RPC

**Симптомы:**
- `error_count > 10`
- Ошибки в логах: `RPC error`, `Connection error`

**Диагностика:**
1. Проверить доступность RPC-ноды: `curl $QUIKNODE_HTTP_URL`
2. Проверить логи на детали ошибок
3. Проверить лимиты QuickNode в дашборде

**Решение:**
- Проверить сетевую доступность
- Проверить лимиты QuickNode
- Рассмотреть переключение на резервный endpoint

---

## Связанные документы

- `app/services/blockchain_service.py` - основной сервис
- `app/services/blockchain/rpc_rate_limiter.py` - RPCRateLimiter
- `app/utils/health_check.py` - health check утилиты
- `app/http_health_server.py` - HTTP endpoint
- `docs/audit/BLOCKCHAIN_SERVICE_AUDIT.md` - аудит использования Web3

---

**Последняя проверка:** 2025-01-16  
**Следующая проверка:** При изменении лимитов или провайдера

