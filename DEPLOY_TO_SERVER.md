# 🚀 Деплой на Production сервер

Пошаговая инструкция по деплою SigmaTrade Bot на production сервер.

---

## 📋 Информация о сервере

- **IP адрес:** 34.88.234.78
- **Внутренний IP:** 10.166.0.3
- **Зона:** europe-north1-a
- **Проект:** telegram-bot-444304
- **ОС:** Debian 12 (bookworm)
- **Пользователь:** konfu
- **Путь проекта:** /opt/sigmatradebot

---

## 🔌 Шаг 1: Подключение к серверу

### Вариант 1: Через gcloud (рекомендуется)
```powershell
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a
```

### Вариант 2: Через SSH (если настроен config)
```powershell
ssh sigmatrade
# или
ssh sigmatrade-direct
```

### Вариант 3: Прямое подключение
```powershell
ssh konfu@34.88.234.78
```

---

## 📥 Шаг 2: Загрузка скрипта деплоя на сервер

После подключения к серверу, загрузите скрипт деплоя:

### Из локальной машины (PowerShell):
```powershell
# Скопировать скрипт на сервер
scp scripts/server-deploy.sh konfu@34.88.234.78:/tmp/
```

### Или создать скрипт прямо на сервере:
```bash
# На сервере
cat > /tmp/server-deploy.sh << 'SCRIPT_END'
# [вставить содержимое scripts/server-deploy.sh]
SCRIPT_END
```

---

## 🚀 Шаг 3: Запуск деплоя

### На сервере выполните:
```bash
# Сделать скрипт исполняемым
chmod +x /tmp/server-deploy.sh

# Запустить деплой
/tmp/server-deploy.sh
```

Скрипт автоматически:
1. ✅ Создаст директорию `/opt/sigmatradebot`
2. ✅ Клонирует репозиторий из GitHub
3. ✅ Настроит `.env` файл (автоматически сгенерирует секреты)
4. ✅ Валидирует переменные окружения
5. ✅ Создаст базу данных PostgreSQL
6. ✅ Проверит готовность к деплою
7. ✅ Соберет Docker образы
8. ✅ Запустит все сервисы (bot, worker, scheduler)
9. ✅ Покажет логи для проверки

---

## ⚙️ Шаг 4: Настройка переменных окружения

Во время выполнения скрипта откроется редактор для `.env` файла.

**Обязательно заполните:**

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_BOT_USERNAME=your_bot_username

# Database (обновите пароль после создания БД)
DATABASE_URL=postgresql+asyncpg://botuser:YOUR_PASSWORD@localhost:5432/sigmatradebot

# Wallet & Blockchain
WALLET_PRIVATE_KEY=your_wallet_private_key_here
WALLET_ADDRESS=0xYourWalletAddress
USDT_CONTRACT_ADDRESS=0x55d398326f99059fF775485246999027B3197955
RPC_URL=https://bsc-dataseed.binance.org/
SYSTEM_WALLET_ADDRESS=0xYourSystemWalletAddress

# Admin IDs (comma-separated)
ADMIN_TELEGRAM_IDS=1040687384

# Остальные переменные уже сгенерированы автоматически
```

---

## 🔍 Шаг 5: Проверка работы

### Проверить статус контейнеров:
```bash
cd /opt/sigmatradebot
docker-compose -f docker-compose.python.yml ps
```

### Просмотреть логи бота:
```bash
docker-compose -f docker-compose.python.yml logs -f bot
```

### Проверить логи worker:
```bash
docker-compose -f docker-compose.python.yml logs -f worker
```

### Проверить логи scheduler:
```bash
docker-compose -f docker-compose.python.yml logs -f scheduler
```

---

## ✅ Шаг 6: Тестирование

1. Откройте Telegram
2. Найдите вашего бота
3. Отправьте команду `/start`
4. Проверьте, что бот отвечает
5. Проверьте регистрацию нового пользователя
6. Проверьте главное меню

---

## 🛠️ Управление сервисами

### Перезапуск всех сервисов:
```bash
cd /opt/sigmatradebot
docker-compose -f docker-compose.python.yml restart
```

### Остановка всех сервисов:
```bash
docker-compose -f docker-compose.python.yml down
```

### Запуск сервисов:
```bash
docker-compose -f docker-compose.python.yml up -d
```

### Просмотр логов всех сервисов:
```bash
docker-compose -f docker-compose.python.yml logs -f
```

---

## 🔧 Устранение проблем

### Бот не отвечает
```bash
# Проверить логи
docker-compose -f docker-compose.python.yml logs bot | tail -50

# Проверить что контейнер запущен
docker-compose -f docker-compose.python.yml ps

# Перезапустить бота
docker-compose -f docker-compose.python.yml restart bot
```

### Ошибки подключения к базе данных
```bash
# Проверить что PostgreSQL запущен
sudo systemctl status postgresql

# Проверить подключение
psql -h localhost -U botuser -d sigmatradebot

# Проверить DATABASE_URL в .env
cat .env | grep DATABASE_URL
```

### Ошибки BlockchainService
```bash
# Проверить RPC_URL
cat .env | grep RPC_URL

# Проверить логи на ошибки подключения
docker-compose -f docker-compose.python.yml logs bot | grep -i "blockchain\|rpc\|bsc"
```

---

## 📊 Мониторинг

### Проверить использование ресурсов:
```bash
docker stats
```

### Проверить место на диске:
```bash
df -h
```

### Проверить логи системы:
```bash
sudo journalctl -u docker -n 50
```

---

## 🔄 Обновление бота

Для обновления бота в будущем:

```bash
cd /opt/sigmatradebot

# Обновить код
git pull origin claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo

# Пересобрать и перезапустить
docker-compose -f docker-compose.python.yml up -d --build
```

---

## 📝 Быстрая команда для деплоя

Если скрипт уже на сервере:

```bash
cd /opt/sigmatradebot
./scripts/server-deploy.sh
```

Или если скрипт в /tmp:

```bash
chmod +x /tmp/server-deploy.sh
/tmp/server-deploy.sh
```

---

## ✅ Чеклист после деплоя

- [ ] Бот отвечает на `/start`
- [ ] Регистрация пользователя работает
- [ ] Главное меню отображается
- [ ] BlockchainService инициализирован (проверить логи)
- [ ] База данных доступна
- [ ] Redis доступен
- [ ] Worker обрабатывает задачи
- [ ] Scheduler запущен
- [ ] Логи не содержат критических ошибок

---

**Готово!** Бот должен быть запущен и работать в production. 🎉

