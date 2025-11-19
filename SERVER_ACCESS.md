# 🔐 Доступ к серверам SigmaTrade Bot

Этот файл содержит всю необходимую информацию для доступа к серверам проекта.

---

## 📋 Информация о сервере

| Параметр | Значение |
|----------|----------|
| **Имя сервера** | sigmatrade-20251108-210354 |
| **Внешний IP** | 34.88.234.78 |
| **Внутренний IP** | 10.166.0.3 |
| **Зона GCP** | europe-north1-a |
| **Проект GCP** | telegram-bot-444304 |
| **ОС** | Debian 12 (bookworm) |
| **Тип машины** | e2-medium |
| **Пользователь (основной)** | konfu |
| **Пользователь (альтернативный)** | mflorinp1978 |
| **Путь проекта** | /opt/sigmatradebot |

---

## 🔑 SSH Ключи

### Публичный ключ (google_compute_engine)

```text
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDXJITOQ0FfX2mZnBxKjC0niB/ZZwco2EyMnig6J+pXUiiSw/TDg++9z8bGC7ee67yxWA809+gl29LfrRsZBcmi+h4NRr2hfVTUMl5MeGIJW1qu4yBmeWY6JMpx+IR23shFGWmvB10HrE+tiJNikqk4DTo/prhkPZQySt3NFF6JrNS41V5u8/kWlp0j7Swnalnhi5MyiQdcxRgbwyg2H5oEBJc6RZsDWXAMwSkA78evXsZ8js3w/018h14KZR01OxuEtiidGn1V0sS1sSZXNRhBYwSAvSm4orXCBgyyhfhEA4OUCnYwS4n4qivrcyUH0gANAc2XCw4H9j6p81FyMXsN PEICHAYCHMO\konfu@PeiChayChmo
```

**Расположение на локальной машине:**

- Windows: `C:\Users\konfu\.ssh\google_compute_engine` (приватный)
- Windows: `C:\Users\konfu\.ssh\google_compute_engine.pub` (публичный)

**Расположение на сервере:**

- Добавлен в: `/home/mflorinp1978/.ssh/authorized_keys`
- Добавлен в: `/home/konfu/.ssh/authorized_keys` (если существует)

---

## 🔌 Способы подключения

### Способ 1: Через gcloud (рекомендуется)

```powershell
# Подключение к серверу
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304

# Выполнение команды без интерактивной сессии
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304 --command="команда"
```

### Способ 2: Через SSH с настроенным config

**SSH Config (C:\Users\konfu\.ssh\config):**

```ssh-config
# ====================================
# SigmaTrade Bot - SSH Configuration
# ====================================

# Вариант 1: Через IAP туннель (безопаснее)
Host sigmatrade
    HostName sigmatrade-20251108-210354
    ProxyCommand C:\Users\konfu\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd compute start-iap-tunnel sigmatrade-20251108-210354 22 --listen-on-stdin --zone=europe-north1-a --project=telegram-bot-444304
    User konfu
    StrictHostKeyChecking no
    IdentityFile C:\Users\konfu\.ssh\google_compute_engine

# Вариант 2: Прямое подключение (быстрее)
Host sigmatrade-direct
    HostName 34.88.234.78
    User konfu
    StrictHostKeyChecking no
    IdentityFile C:\Users\konfu\.ssh\google_compute_engine
```

**Использование:**

```powershell
# Через IAP туннель
ssh sigmatrade

# Прямое подключение
ssh sigmatrade-direct
```

### Способ 3: Прямое подключение по IP

```powershell
ssh -i C:\Users\konfu\.ssh\google_compute_engine konfu@34.88.234.78
```

---

## 📤 Копирование файлов

### Через gcloud scp

```powershell
# Копирование файла на сервер
gcloud compute scp local-file.txt sigmatrade-20251108-210354:/tmp/ --zone=europe-north1-a --project=telegram-bot-444304

# Копирование файла с сервера
gcloud compute scp sigmatrade-20251108-210354:/path/to/file.txt . --zone=europe-north1-a --project=telegram-bot-444304

# Копирование директории
gcloud compute scp --recurse ./local-dir sigmatrade-20251108-210354:/tmp/ --zone=europe-north1-a --project=telegram-bot-444304
```

### Через обычный scp

```powershell
# С использованием SSH config
scp file.txt sigmatrade:/tmp/

# Прямое подключение
scp -i C:\Users\konfu\.ssh\google_compute_engine file.txt konfu@34.88.234.78:/tmp/
```

---

## 🚀 Быстрые команды для деплоя

### Подключение и переход в проект

```bash
# Подключиться к серверу
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304

# На сервере: перейти в проект
cd /opt/sigmatradebot
```

### Проверка статуса

```bash
# Статус контейнеров
docker-compose -f docker-compose.python.yml ps

# Логи бота
docker-compose -f docker-compose.python.yml logs -f bot

# Логи worker
docker-compose -f docker-compose.python.yml logs -f worker

# Логи scheduler
docker-compose -f docker-compose.python.yml logs -f scheduler
```

### Управление сервисами

```bash
# Перезапуск
docker-compose -f docker-compose.python.yml restart

# Остановка
docker-compose -f docker-compose.python.yml down

# Запуск
docker-compose -f docker-compose.python.yml up -d

# Пересборка и запуск
docker-compose -f docker-compose.python.yml up -d --build
```

---

## 🔧 Полезные команды GCP

### Управление инстансом

```powershell
# Проверить статус
gcloud compute instances describe sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304 --format="get(status)"

# Остановить сервер
gcloud compute instances stop sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304

# Запустить сервер
gcloud compute instances start sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304

# Список всех инстансов
gcloud compute instances list --project=telegram-bot-444304
```

### Проверка проекта

```powershell
# Текущий проект
gcloud config get-value project

# Установить проект
gcloud config set project telegram-bot-444304
```

---

## 📝 Настройка .env на сервере

### Обязательные переменные

```bash
# На сервере
cd /opt/sigmatradebot
nano .env
```

**Заполнить:**

- `TELEGRAM_BOT_TOKEN` - токен от @BotFather
- `WALLET_PRIVATE_KEY` - приватный ключ кошелька
- `WALLET_ADDRESS` - адрес кошелька (0x...)
- `USDT_CONTRACT_ADDRESS` - адрес USDT на BSC (`0x55d398326f99059fF775485246999027B3197955`)
- `RPC_URL` - BSC RPC endpoint (`https://bsc-dataseed.binance.org/`)
- `SYSTEM_WALLET_ADDRESS` - системный кошелек
- `ADMIN_TELEGRAM_IDS` - ID админов через запятую (`1040687384`)
- `DATABASE_URL` - строка подключения к PostgreSQL

---

## 🗄️ Настройка базы данных

```bash
# На сервере
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создать БД и пользователя
sudo -u postgres psql << EOF
CREATE DATABASE sigmatradebot;
CREATE USER botuser WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE sigmatradebot TO botuser;
\q
EOF

# Обновить DATABASE_URL в .env
# DATABASE_URL=postgresql+asyncpg://botuser:your_secure_password@localhost:5432/sigmatradebot
```

---

## 🔄 Деплой бота

### Полный деплой (первый раз)

```bash
# На сервере
cd /opt/sigmatradebot

# Клонировать/обновить репозиторий
git clone -b claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo https://github.com/Avertenandor/sigmatradebot.git .
# или если уже клонирован:
git pull origin claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo

# Настроить .env (см. выше)

# Запустить деплой
chmod +x scripts/deploy-non-interactive.sh
./scripts/deploy-non-interactive.sh
```

### Обновление бота

```bash
cd /opt/sigmatradebot
git pull origin claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo
docker-compose -f docker-compose.python.yml up -d --build
```

---

## 🐛 Устранение проблем

### Проблема: Permission denied при SSH

**Решение:**

1. Проверить что ключ добавлен в `authorized_keys` на сервере
2. Проверить права: `chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys`
3. Использовать gcloud для подключения

### Проблема: Не могу подключиться через gcloud

**Решение:**

```powershell
# Проверить что сервер запущен
gcloud compute instances list --project=telegram-bot-444304

# Проверить проект
gcloud config get-value project

# Установить правильный проект
gcloud config set project telegram-bot-444304
```

### Проблема: Docker permission denied

**Решение:**

```bash
# На сервере
sudo usermod -aG docker $USER
# Переподключиться
exit
ssh sigmatrade
```

---

## 📚 Дополнительная информация

- **GCP Console:** <https://console.cloud.google.com/compute/instancesDetail/zones/europe-north1-a/instances/sigmatrade-20251108-210354?project=telegram-bot-444304>
- **Документация деплоя:** `docs/deployment/DEPLOYMENT.md`
- **Настройка сервера:** `docs/deployment/SIGMATRADE_SERVER_SETUP.md`

---

## 🔒 Безопасность

⚠️ **ВАЖНО:**

- Этот файл содержит публичные ключи (безопасно)
- НЕ коммитьте приватные ключи в репозиторий
- Приватные ключи должны быть только в `C:\Users\konfu\.ssh\`
- Используйте `.gitignore` для исключения файлов с секретами

---

**Дата создания:** 2025-01-15  
**Последнее обновление:** 2025-01-15  
**Версия:** 1.0
