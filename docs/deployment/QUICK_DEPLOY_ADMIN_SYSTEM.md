# 🚀 Быстрый деплой системы управления админами

## Вариант 1: Автоматический деплой (PowerShell)

### На Windows (PowerShell):

```powershell
# Перейти в директорию проекта
cd C:\Users\konfu\Desktop\sigmatradebot

# Запустить скрипт деплоя
.\scripts\deploy-admin-system.ps1
```

Скрипт автоматически:
1. ✅ Загрузит скрипт деплоя на сервер
2. ✅ Подключится к серверу
3. ✅ Обновит код из репозитория
4. ✅ Применит миграцию БД
5. ✅ Пересоберет и перезапустит сервисы

---

## Вариант 2: Ручной деплой

### Шаг 1: Подключиться к серверу

```powershell
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304
```

### Шаг 2: Загрузить скрипт на сервер

```powershell
# В PowerShell (на локальной машине)
gcloud compute scp scripts\deploy-admin-system.sh sigmatrade-20251108-210354:/tmp/ --zone=europe-north1-a --project=telegram-bot-444304
```

### Шаг 3: Запустить скрипт на сервере

```bash
# На сервере
chmod +x /tmp/deploy-admin-system.sh
/tmp/deploy-admin-system.sh
```

---

## Вариант 3: Пошаговый деплой вручную

### 1. Подключиться к серверу

```powershell
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304
```

### 2. Обновить код

```bash
cd /opt/sigmatradebot
git pull origin claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo
```

### 3. Применить миграцию

```bash
# Через Docker
docker-compose -f docker-compose.python.yml exec bot alembic upgrade head

# Или локально (если alembic установлен)
alembic upgrade head
```

### 4. Перезапустить сервисы

```bash
docker-compose -f docker-compose.python.yml up -d --build
```

### 5. Проверить логи

```bash
docker-compose -f docker-compose.python.yml logs -f bot | tail -50
```

---

## ⚠️ ВАЖНО перед деплоем

1. **Убедитесь, что код закоммичен и запушен в репозиторий:**
   ```bash
   git status
   git add .
   git commit -m "feat: Add admin management system"
   git push
   ```

2. **Проверьте, что миграция существует:**
   ```bash
   ls alembic/versions/20250113_000001_create_admin_actions_table.py
   ```

---

## ✅ Проверка после деплоя

### 1. Проверить миграцию

```bash
# На сервере
docker-compose -f docker-compose.python.yml exec bot alembic current
```

Должно показать: `20250113_000001`

### 2. Проверить таблицу в БД

```bash
# На сервере
docker-compose -f docker-compose.python.yml exec bot python -c "
from app.models.admin_action import AdminAction
print('✅ AdminAction model imported successfully')
"
```

### 3. Проверить логи

```bash
# На сервере
docker-compose -f docker-compose.python.yml logs bot | grep -i "admin\|middleware" | tail -20
```

### 4. Тест в Telegram

1. Откройте бота в Telegram
2. Отправьте `/admin`
3. Система должна запросить мастер-ключ
4. Введите мастер-ключ
5. Должна открыться админ-панель

---

## 🐛 Устранение проблем

### Проблема: Миграция не применяется

```bash
# Проверить текущую версию
docker-compose -f docker-compose.python.yml exec bot alembic current

# Применить вручную
docker-compose -f docker-compose.python.yml exec bot alembic upgrade head
```

### Проблема: Бот не запускается

```bash
# Проверить логи на ошибки
docker-compose -f docker-compose.python.yml logs bot | grep -i error

# Проверить импорты
docker-compose -f docker-compose.python.yml exec bot python -c "from app.models.admin_action import AdminAction"
```

### Проблема: Скрипт не запускается

```bash
# Проверить права
chmod +x /tmp/deploy-admin-system.sh

# Запустить с выводом ошибок
bash -x /tmp/deploy-admin-system.sh
```

---

## 📝 Быстрая команда (все в одной строке)

```bash
cd /opt/sigmatradebot && \
git pull && \
docker-compose -f docker-compose.python.yml exec bot alembic upgrade head && \
docker-compose -f docker-compose.python.yml up -d --build && \
docker-compose -f docker-compose.python.yml logs bot | tail -50
```

---

**Рекомендуется использовать Вариант 1 (автоматический деплой) для простоты!** ✅

