# 🚀 ДЕПЛОЙ СИСТЕМЫ УПРАВЛЕНИЯ АДМИНАМИ - ИНСТРУКЦИЯ

## ✅ Статус: Все готово к деплою!

Все файлы созданы и готовы. Теперь нужно задеплоить на сервер.

---

## 📋 Шаг 1: Закоммитить изменения (если еще не сделано)

```powershell
# В PowerShell
cd C:\Users\konfu\Desktop\sigmatradebot

# Проверить статус
git status

# Добавить все изменения
git add .

# Закоммитить
git commit -m "feat: Add admin management system with master key auth, logging, and auto-logout"

# Отправить на сервер
git push origin claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo
```

---

## 🚀 Шаг 2: Задеплоить на сервер

### Вариант A: Автоматический деплой (РЕКОМЕНДУЕТСЯ)

```powershell
# В PowerShell
cd C:\Users\konfu\Desktop\sigmatradebot
.\scripts\deploy-admin-system.ps1
```

Скрипт автоматически выполнит все шаги!

### Вариант B: Ручной деплой

#### 1. Подключиться к серверу:

```powershell
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304
```

#### 2. На сервере выполнить:

```bash
cd /opt/sigmatradebot

# Обновить код
git pull origin claude/sigmatradebot-python-migration-01UUhWd7yPartmZdGxtPAFLo

# Применить миграцию
docker-compose -f docker-compose.python.yml exec bot alembic upgrade head

# Перезапустить сервисы
docker-compose -f docker-compose.python.yml up -d --build

# Проверить логи
docker-compose -f docker-compose.python.yml logs bot | tail -50
```

---

## ✅ Шаг 3: Проверка после деплоя

### 1. Проверить миграцию:

```bash
# На сервере
docker-compose -f docker-compose.python.yml exec bot alembic current
```

Должно показать: `20250113_000001`

### 2. Проверить таблицу в БД:

```bash
# На сервере
docker-compose -f docker-compose.python.yml exec bot python -c "from app.models.admin_action import AdminAction; print('OK')"
```

### 3. Тест в Telegram:

1. Откройте бота
2. Отправьте `/admin`
3. Система должна запросить мастер-ключ
4. Введите мастер-ключ
5. Должна открыться админ-панель

---

## 📝 Что было добавлено

### Новые файлы:
- ✅ `app/models/admin_action.py` - Модель логирования
- ✅ `app/repositories/admin_action_repository.py` - Репозиторий
- ✅ `app/services/admin_log_service.py` - Сервис логирования
- ✅ `bot/middlewares/admin_auth_middleware.py` - Middleware аутентификации
- ✅ `bot/handlers/admin/admins.py` - Handlers управления админами
- ✅ `jobs/tasks/admin_session_cleanup.py` - Задача очистки сессий
- ✅ `alembic/versions/20250113_000001_create_admin_actions_table.py` - Миграция

### Обновленные файлы:
- ✅ `app/models/admin_session.py` - Добавлен метод `is_inactive()`
- ✅ `app/services/admin_service.py` - Обновлена проверка бездействия
- ✅ `bot/handlers/admin/panel.py` - Handler для ввода мастер-ключа
- ✅ `bot/handlers/admin/users.py` - Логирование блокировки/терминации
- ✅ `bot/handlers/admin/withdrawals.py` - Логирование одобрения/отклонения
- ✅ `bot/handlers/admin/broadcast.py` - Логирование рассылок
- ✅ `bot/keyboards/reply.py` - Обновлена клавиатура админа
- ✅ `bot/main.py` - Интегрирован middleware
- ✅ `jobs/scheduler.py` - Добавлена задача очистки

---

## ⚠️ ВАЖНО после деплоя

1. **Все админы должны будут ввести мастер-ключ при первом входе**
2. **Мастер-ключ отправляется новому админу автоматически при создании**
3. **Сессии автоматически завершаются при бездействии > 15 минут**
4. **Все действия админов логируются в таблицу `admin_actions`**

---

## 🐛 Если что-то пошло не так

### Проблема: Миграция не применяется

```bash
# На сервере
docker-compose -f docker-compose.python.yml exec bot alembic upgrade head
```

### Проблема: Бот не запускается

```bash
# На сервере - проверить логи
docker-compose -f docker-compose.python.yml logs bot | grep -i error
```

### Проблема: Middleware не работает

```bash
# На сервере - проверить импорты
docker-compose -f docker-compose.python.yml exec bot python -c "from bot.middlewares.admin_auth_middleware import AdminAuthMiddleware"
```

---

## 📚 Дополнительная документация

- `docs/ADMIN_MANAGEMENT_SYSTEM.md` - Полная документация
- `docs/ADMIN_SYSTEM_TESTING.md` - Инструкция по тестированию
- `docs/DEPLOY_ADMIN_SYSTEM.md` - Детальная инструкция по деплою
- `QUICK_DEPLOY_ADMIN_SYSTEM.md` - Быстрая инструкция

---

**Готово к деплою! Выберите вариант деплоя выше и следуйте инструкциям.** ✅

