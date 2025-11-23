# 🔐 Доступ к серверам SigmaTrade Bot

Этот файл содержит всю необходимую информацию для доступа к серверам проекта.

---

## 📋 Информация о сервере

| Параметр | Значение |
|----------|----------|
| **Имя сервера** | sigmatrade-20251108-210354 |
| **Внешний IP** | 34.88.234.78 |
| **Внутренний IP** | 10.166.0.3 (GCP internal) |
| **Зона GCP** | europe-north1-a |
| **Проект GCP** | telegram-bot-444304 |
| **ОС** | Debian GNU/Linux (6.1.0-40-cloud-amd64) |
| **Тип машины** | e2-medium |
| **Пользователь (основной)** | mflorinp1978 |
| **Пользователь (Windows)** | konfu |
| **Путь проекта** | /opt/sigmatradebot |

---

## 🔑 SSH Ключи

### ⚠️ КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ О БЕЗОПАСНОСТИ ⚠️

**🔴 ЭТОТ РАЗДЕЛ СОДЕРЖИТ ПРИВАТНЫЙ SSH КЛЮЧ!**

Приватный ключ - это как мастер-ключ от вашего сервера. Любой, кто получит доступ к этому ключу, сможет:
- Подключиться к вашему серверу
- Читать и изменять все файлы
- Удалять данные
- Компрометировать весь проект

**ОБЯЗАТЕЛЬНЫЕ МЕРЫ БЕЗОПАСНОСТИ:**
1. ❌ **НИКОГДА не загружайте этот файл в GitHub или другие публичные репозитории**
2. ❌ **НИКОГДА не отправляйте через email, мессенджеры или незащищенные каналы**
3. ✅ **Храните только на защищенных устройствах**
4. ✅ **Используйте .gitignore для исключения:**
   ```gitignore
   SERVER_ACCESS.md
   *_ACCESS.md
   *.pem
   *.key
   id_rsa*
   google_compute_engine*
   ```
5. ✅ **Регулярно проверяйте что файл не попал в git:**
   ```bash
   git status
   git ls-files | grep -i access
   ```

---

### Публичный ключ (google_compute_engine.pub)

**✅ БЕЗОПАСНО - можно делиться**

```text
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDXJITOQ0FfX2mZnBxKjC0niB/ZZwco2EyMnig6J+pXUiiSw/TDg++9z8bGC7ee67yxWA809+gl29LfrRsZBcmi+h4NRr2hfVTUMl5MeGIJW1qu4yBmeWY6JMpx+IR23shFGWmvB10HrE+tiJNikqk4DTo/prhkPZQySt3NFF6JrNS41V5u8/kWlp0j7Swnalnhi5MyiQdcxRgbwyg2H5oEBJc6RZsDWXAMwSkA78evXsZ8js3w/018h14KZR01OxuEtiidGn1V0sS1sSZXNRhBYwSAvSm4orXCBgyyhfhEA4OUCnYwS4n4qivrcyUH0gANAc2XCw4H9j6p81FyMXsN PEICHAYCHMO\konfu@PeiChayChmo
```

### Приватный ключ (google_compute_engine)

**🔴 КОНФИДЕНЦИАЛЬНО - НИКОГДА НЕ ДЕЛИТЬСЯ!**

```text
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1ySEzkNBX19pmZwcSowtJ4gf2WcHKNhMjJ4oOifqV1IoksP0
w4Pvvc/Gxgu3nuu8sVgPNPfoJdvS360bGQXJovoeDUa9oX1U1DJeTHhiCVtaruMg
ZnlmOiTKcfiEdt7IRRlprwddB6xPrYiTYpKpOA06P6a4ZD2UMkrdzRReiazUuNVe
bvP5FpadI+0sJ2pZ4YuTMokHXMUYG8MoNh+aBASXOkWbA1lwDMEpAO/Hr17GfI7N
8P9NfIdeCmUdNTsbhLYonRp9VdLEtbEmVzUYQWMEgL0puKK1wgYMsoX4RAODlAp2
MEuJ+Kor63MlB9IADQHNlwsOB/Y+qfNRcjF7DQIDAQABAoIBADX0nqnsDBUTJLS1
hhLcHObxKKupPw5rUKdjcstC/25u2GYWZugxyopb9Yntnlto26XOY+Hw2nPEMZqP
G2CnJu6Ms8S4nQ5HFGMzTpr3Bf86vf9mTtXkVFL4rxzuKqp1LNzHhs2ylw45lLH8
spniFjZMevNDqLLbDrOeOwoXta3pCIrRk6Fgb0Obrg5sS7b8+sJxTBYCLN3T/ufL
pFjJ7a34w2CaHygvStr5bn1IhWDfxguCuNs2lKurfNDMfvQN+8VAabDknQ15j5e5
Ag27osHnb/lo4I3BUjI9YvoJY4Q4zsbjVlgpDza8tQkFuSSKUHSCBUYYtbsEavOZ
Ca7ArrECgYEA4FQe/lEqzP6smQ4if8R5u6HEXZV/LYaMoXBXkZUa7YVPcSVoEYDF
cb47lfWSaIv8X/bhHuUjhL6J4rJBWb+aNrdAcbA7gBW4ZZpve6mf5YjG8901HEa1
2bFIN6hNwJOALNV4hwdKB/7ciMlGqHjdMBSgLP0chjqMO0p9EnItbwMCgYEA9YRk
KR6oNFEPzri83wyj9Yspu3MS5vuGtCpKURfLEW0ZrwAoXaz3wRcxYZiugpEEtvcu
ZQBHcbuuuWSUaOz8K1c1D6+HnHZjzysSafcyoNj4/Z+X2MI0IllkeMd8+ZyCS5jY
ITJcSreD0AbHtcdpHX4bEsytXXDskWv8HRxjiK8CgYBY8eGsEoC28Q98TDdvk3Z0
5+oU9Q6M/XlLFWETLxyTKrVZ9mvx7K3csIGtrsXTQBXb8uZFurK/klDXmrgAntDF
exlJOogM/A+18WrcjGACwZ2o2X+Sa5L08q7gqpHRlmpO3IFCgKhgzTOh5LRoXivN
QZBU5jLmIdayN5Gpu626AwKBgQDiIGrD+KmBbfu6MSo74X+Novvv2t/ZAGcjvyOt
ptVwmmSiaunCxZF3NW5U7nQka37FKcqAWg5zcSJPPJT4QvVK0cpcRRYJBH2PDKOs
F3J49P33UqtfiBbOYDkKiOnRWNYk3ISLpr+cTYPI8MW15hEpicFTwlIWkvBATA3r
nf8KnwKBgQCiUjXGY6LLITLtnXUNcZArABP7ilCJWWSq9aqothFJmfp6itJV+nBd
p+bXjQN4MBQeBAnQ4xrvpU4kmjh8HWPGUa13iTiN8XQbDfmuMDxGrejghKbNr3QA
OSUehd/29lKTVGOwQyUbsWWGVLq2FMf0mVwRFgNCXejWBXWCDVj9CQ==
-----END RSA PRIVATE KEY-----
```

**Расположение ключей:**

- **На Windows (локально):**
  - Приватный: `C:\Users\konfu\.ssh\google_compute_engine` 🔴 КОНФИДЕНЦИАЛЬНО
  - Публичный: `C:\Users\konfu\.ssh\google_compute_engine.pub` ✅ Безопасно

- **На сервере:**
  - Публичный ключ добавлен в: `/home/mflorinp1978/.ssh/authorized_keys`
  - Приватный ключ НЕ должен быть на сервере!

**⚠️ ВАЖНО:** Ключ для Cursor IDE называется `google_compute_engine`, а НЕ `claude_key`!

### Использование приватного ключа

**Для SSH подключения:**
```powershell
ssh -i C:\Users\konfu\.ssh\google_compute_engine mflorinp1978@34.88.234.78
```

**Для SCP (копирование файлов):**
```powershell
scp -i C:\Users\konfu\.ssh\google_compute_engine file.txt mflorinp1978@34.88.234.78:/tmp/
```

**Для Cursor IDE:**
Ключ автоматически используется через SSH config (см. раздел "Настройка Cursor IDE")

### Восстановление ключа на новом компьютере

Если нужно настроить доступ на новом компьютере:

1. **Создайте файл приватного ключа:**
   ```powershell
   # Создать папку .ssh если её нет
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh"
   
   # Создать файл приватного ключа
   notepad "$env:USERPROFILE\.ssh\google_compute_engine"
   ```

2. **Скопируйте содержимое приватного ключа** (из раздела выше) в файл

3. **Создайте файл публичного ключа:**
   ```powershell
   notepad "$env:USERPROFILE\.ssh\google_compute_engine.pub"
   ```

4. **Скопируйте содержимое публичного ключа** в файл

5. **Настройте SSH config** (см. раздел "Способы подключения")

### Создание нового SSH ключа (если текущий скомпрометирован)

```powershell
# На Windows в PowerShell
ssh-keygen -t rsa -b 4096 -f "$env:USERPROFILE\.ssh\google_compute_engine_new" -N ""

# Показать новый публичный ключ
cat "$env:USERPROFILE\.ssh\google_compute_engine_new.pub"
```

Затем на сервере:
```bash
# Добавить новый публичный ключ
echo "СКОПИРОВАННЫЙ_ПУБЛИЧНЫЙ_КЛЮЧ" >> ~/.ssh/authorized_keys

# Удалить старый скомпрометированный ключ
nano ~/.ssh/authorized_keys
# Удалите строку со старым ключом

# Проверить права
chmod 600 ~/.ssh/authorized_keys
```

---

## 🔌 Способы подключения

### Способ 1: Через gcloud (рекомендуется)

```powershell
# Подключение к серверу sigmatrade
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304

# Выполнение команды без интерактивной сессии
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304 --command="команда"
```

### Способ 2: Через SSH с настроенным config

**SSH Config (C:\Users\konfu\.ssh\config):**

```ssh-config
# ====================================
# Второй сервер - SigmaTrade Bot
# ====================================
# Вариант 1: Через IAP туннель (рекомендуется)
Host sigmatrade
    HostName sigmatrade-20251108-210354
    ProxyCommand C:\Users\konfu\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd compute start-iap-tunnel sigmatrade-20251108-210354 22 --listen-on-stdin --zone=europe-north1-a --project=telegram-bot-444304
    User mflorinp1978
    IdentityFile C:\Users\konfu\.ssh\google_compute_engine
    StrictHostKeyChecking no
    UserKnownHostsFile=NUL

# Вариант 2: Прямое подключение (запасной)
Host sigmatrade-direct
    HostName 34.88.234.78
    User mflorinp1978
    IdentityFile C:\Users\konfu\.ssh\google_compute_engine
    StrictHostKeyChecking no
    UserKnownHostsFile=NUL
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
ssh -i C:\Users\konfu\.ssh\google_compute_engine mflorinp1978@34.88.234.78
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
scp -i C:\Users\konfu\.ssh\google_compute_engine file.txt mflorinp1978@34.88.234.78:/tmp/
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

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=8490693145:AAEECwr4c-S-PuHVIccFCw4mMpH0-Uq_rhs
ADMIN_TELEGRAM_IDS=1040687384

# BSC QuickNode RPC Configuration
RPC_URL=https://old-patient-butterfly.bsc.quiknode.pro/4f77305d4e6f7ce51cace16a02b88659c7ec249d
WSS_URL=wss://old-patient-butterfly.bsc.quiknode.pro/4f77305d4e6f7ce51cace16a02b88659c7ec249d
QUICKNODE_API_KEY=4f77305d4e6f7ce51cace16a02b88659c7ec249d

# Blockchain Contracts
USDT_CONTRACT_ADDRESS=0x55d398326f99059fF775485246999027B3197955

# Wallet Configuration (ЗАПОЛНИТЬ)
WALLET_PRIVATE_KEY=ваш_приватный_ключ_кошелька
WALLET_ADDRESS=0x...
SYSTEM_WALLET_ADDRESS=0x...

# Database Configuration (ЗАПОЛНИТЬ)
DATABASE_URL=postgresql+asyncpg://botuser:your_secure_password@localhost:5432/sigmatradebot
```

### Детальное описание переменных окружения

#### Telegram настройки:
- **TELEGRAM_BOT_TOKEN**: `8490693145:AAEECwr4c-S-PuHVIccFCw4mMpH0-Uq_rhs`
  - Токен бота от @BotFather
  - Используется для подключения к Telegram API
  
- **ADMIN_TELEGRAM_IDS**: `1040687384`
  - ID главного администратора
  - Можно добавить несколько через запятую: `1040687384,123456789,987654321`

#### BSC QuickNode настройки:
- **RPC_URL**: `https://old-patient-butterfly.bsc.quiknode.pro/4f77305d4e6f7ce51cace16a02b88659c7ec249d`
  - HTTP endpoint для взаимодействия с BSC blockchain
  - Используется для отправки транзакций и чтения данных
  
- **WSS_URL**: `wss://old-patient-butterfly.bsc.quiknode.pro/4f77305d4e6f7ce51cace16a02b88659c7ec249d`
  - WebSocket endpoint для real-time событий
  - Используется для отслеживания транзакций в реальном времени
  
- **QUICKNODE_API_KEY**: `4f77305d4e6f7ce51cace16a02b88659c7ec249d`
  - API ключ для QuickNode
  - Обеспечивает доступ к ноде BSC

#### Blockchain контракты:
- **USDT_CONTRACT_ADDRESS**: `0x55d398326f99059fF775485246999027B3197955`
  - Официальный адрес USDT (Tether) на Binance Smart Chain
  - Используется для операций с USDT

#### Кошельки (НУЖНО ЗАПОЛНИТЬ):
- **WALLET_PRIVATE_KEY**: Приватный ключ основного кошелька бота
- **WALLET_ADDRESS**: Публичный адрес основного кошелька (0x...)
- **SYSTEM_WALLET_ADDRESS**: Адрес системного кошелька для сбора комиссий

#### База данных (НУЖНО ЗАПОЛНИТЬ):
- **DATABASE_URL**: Строка подключения к PostgreSQL
  - Формат: `postgresql+asyncpg://username:password@host:port/database`

---

## 🔗 QuickNode Endpoints

### HTTP Endpoint
```
https://old-patient-butterfly.bsc.quiknode.pro/4f77305d4e6f7ce51cace16a02b88659c7ec249d
```

**Использование:**
- Отправка транзакций
- Чтение состояния blockchain
- Вызов смарт-контрактов
- Получение баланса кошельков

### WebSocket Endpoint
```
wss://old-patient-butterfly.bsc.quiknode.pro/4f77305d4e6f7ce51cace16a02b88659c7ec249d
```

**Использование:**
- Real-time мониторинг транзакций
- Подписка на события контрактов
- Отслеживание новых блоков
- Push-уведомления о событиях

### API Key
```
4f77305d4e6f7ce51cace16a02b88659c7ec249d
```

**Тестирование подключения:**

```bash
# Проверка HTTP endpoint
curl -X POST https://old-patient-butterfly.bsc.quiknode.pro/4f77305d4e6f7ce51cace16a02b88659c7ec249d \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Должен вернуть текущий номер блока
```

**Полезные ссылки:**
- QuickNode Dashboard: https://dashboard.quiknode.io/
- BSC Testnet: https://testnet.bscscan.com/
- BSC Mainnet: https://bscscan.com/

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

- **GCP Console:** <https://console.cloud.google.com/compute/instances?project=telegram-bot-444304>
- **Сервер SigmaTrade:** <https://console.cloud.google.com/compute/instancesDetail/zones/europe-north1-a/instances/sigmatrade-20251108-210354?project=telegram-bot-444304>
- **Документация деплоя:** `docs/deployment/DEPLOYMENT.md`
- **Настройка сервера:** `docs/deployment/SIGMATRADE_SERVER_SETUP.md`

---

## 💻 Настройка Cursor IDE

### Подключение к серверу через Cursor

**Шаг 1: Убедитесь что SSH config настроен** (см. выше)

**Шаг 2: В Cursor IDE:**

1. Нажмите **F1** (или Ctrl+Shift+P)
2. Введите: `Remote-SSH: Connect to Host`
3. Выберите: **sigmatrade** (для IAP туннеля) или **sigmatrade-direct** (для прямого подключения)
4. Дождитесь подключения
5. Откройте папку: `/opt/sigmatradebot`

**Шаг 3: Работа с проектом**

Теперь вы можете:
- Редактировать файлы на сервере через Cursor
- Использовать AI-ассистентов для работы с кодом
- Запускать команды в терминале Cursor (который работает на сервере)
- Отлаживать код прямо на сервере

### Проверка подключения

```bash
# В терминале Cursor (должен показать сервер)
hostname
# Должно вывести: sigmatrade-20251108-210354

# Проверка проекта
pwd
# Должно быть: /opt/sigmatradebot или /home/mflorinp1978
```

### Быстрая настройка нового ключа для Cursor

Если нужно создать новый SSH ключ:

```powershell
# На Windows PowerShell
# 1. Показываем публичный ключ
cat $env:USERPROFILE\.ssh\google_compute_engine.pub

# 2. Копируем вывод
```

На сервере:

```bash
# Добавляем ключ
echo "" >> ~/.ssh/authorized_keys
echo "# google_compute_engine key for Cursor IDE" >> ~/.ssh/authorized_keys
echo "ВСТАВЬТЕ_СКОПИРОВАННЫЙ_ПУБЛИЧНЫЙ_КЛЮЧ" >> ~/.ssh/authorized_keys

# Устанавливаем права
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# Проверяем
tail -3 ~/.ssh/authorized_keys
```

### Обновление SSH config

```powershell
# Открыть config в блокноте
notepad $env:USERPROFILE\.ssh\config
```

**Убедитесь что указаны:**
- Правильный User: `mflorinp1978` (НЕ `konfu`!)
- Правильный IdentityFile: `C:\Users\konfu\.ssh\google_compute_engine`
- Правильный HostName для сервера

---

## 🔧 История решения проблем

### Проблема: Cursor IDE удалил SSH ключи (22.11.2025)

**Симптомы:**
- AI-ассистенты в Cursor случайно удалили SSH ключи
- Потерян доступ к серверу из Cursor
- Нужно было восстановить доступ

**Решение:**

1. **Обнаружили что ключ называется не `claude_key`, а `google_compute_engine`**
   - Ключ был на Windows: `C:\Users\konfu\.ssh\google_compute_engine`
   - Но не был добавлен в `authorized_keys` на сервере

2. **Нашли несоответствие пользователей:**
   - В SSH config был указан `User konfu`
   - На сервере пользователь `mflorinp1978`
   - Исправили в config на правильного пользователя

3. **Добавили публичный ключ на сервер:**
   ```bash
   # Скопировали публичный ключ с Windows
   cat $env:USERPROFILE\.ssh\google_compute_engine.pub
   
   # Добавили на сервер в authorized_keys
   echo "# google_compute_engine key for Cursor IDE" >> ~/.ssh/authorized_keys
   echo "ssh-rsa AAAA..." >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

4. **Обновили SSH config:**
   - Изменили `User konfu` → `User mflorinp1978`
   - Добавили явный `IdentityFile`

5. **Результат:** Cursor IDE успешно подключился к серверу! ✅

**Уроки:**
- ✅ SSH ключи могут иметь разные имена (google_compute_engine, claude_key, id_rsa)
- ✅ Всегда проверять соответствие пользователя в config и на сервере
- ✅ Публичный ключ ДОЛЖЕН быть в authorized_keys на сервере
- ✅ Приватный ключ должен быть указан в SSH config через IdentityFile

---

## 🔒 Безопасность

⚠️ **КРИТИЧЕСКИ ВАЖНО:**

### Что содержит этот документ:

**✅ БЕЗОПАСНО (публичная информация):**
- SSH публичные ключи
- IP адреса серверов
- Имена серверов и проектов
- Публичные адреса смарт-контрактов

**🔴 КОНФИДЕНЦИАЛЬНО (НЕ ДЕЛИТЬСЯ):**
- **Telegram Bot Token**: 8490693145:AAErJ2-vxNnnjXU2dS3i4u6hxVbw-JhtLlo
- **QuickNode API Key**: `4f77305d4e6f7ce51cace16a02b88659c7ec249d`
- **QuickNode Endpoints** (содержат API ключ в URL)
- **Admin Telegram ID**: `1040687384`
- SSH приватные ключи (в `C:\Users\konfu\.ssh\`)

**❌ НИКОГДА НЕ ДОБАВЛЯТЬ В ЭТОТ ФАЙЛ:**
- Приватные ключи кошельков (WALLET_PRIVATE_KEY)
- Пароли от баз данных
- Seed фразы
- Приватные ключи SSH (только публичные)

### Правила безопасности:

1. **НЕ коммитьте этот файл в публичный GitHub репозиторий**
2. **Храните локальную копию только на защищённых устройствах**
3. **НЕ отправляйте этот файл через незащищённые каналы**
4. **Регулярно ротируйте API ключи и токены**
5. **Используйте `.gitignore` для исключения:**
   ```gitignore
   .env
   .env.*
   *_ACCESS.md
   *.pem
   *.key
   id_rsa*
   google_compute_engine
   ```

### Что делать при компрометации:

**Если скомпрометирован Telegram Bot Token:**
1. Зайти к @BotFather в Telegram
2. Отозвать старый токен: `/revoke`
3. Создать новый токен: `/newbot` или `/token`
4. Обновить в .env на сервере
5. Перезапустить бота

**Если скомпрометирован QuickNode API Key:**
1. Зайти в QuickNode Dashboard: https://dashboard.quiknode.io/
2. Удалить скомпрометированный endpoint
3. Создать новый endpoint
4. Обновить RPC_URL и WSS_URL в .env
5. Перезапустить все сервисы

**Если скомпрометированы SSH ключи:**
1. Немедленно удалить публичный ключ из `~/.ssh/authorized_keys` на сервере
2. Создать новую пару ключей
3. Добавить новый публичный ключ на сервер
4. Обновить SSH config на локальной машине

---

**Дата создания:** 2025-01-15  
**Последнее обновление:** 2025-11-22  
**Версия:** 2.0



что касается работы с сервером и серверами вообще всегда проверяй хендлеры. роутеры, миграции, кеширование докера, запоминай удачные решения и обучайся в процессе, проверяй что контейнеры обновились на сервере, 