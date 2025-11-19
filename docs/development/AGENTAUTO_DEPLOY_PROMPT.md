# ТЕХЗАДАНИЕ ДЛЯ AGENTAUTO (CURSOR)

## ТЕМА: ПРОДАКШЕН-ДЕПЛОЙ SIGMATRADE BOT НА GCP

---

## ОБЩИЕ ПРАВИЛА РАБОТЫ

1. Ты работаешь в IDE Cursor как AgentAuto.

2. У тебя есть:
   - локальный проект с репозиторием SigmaTrade Bot;
   - доступ к серверу GCP по SSH;
   - доступ к терминалу внутри Cursor.

3. Все действия с кодом, тестами и деплоем ты обязан выполнять РЕАЛЬНЫМИ КОМАНДАМИ через терминал, а не "симулировать".

4. Рабочая версия бота — ТОЛЬКО Python:
   - Python 3.11 + aiogram 3.x;
   - каталоги `app/`, `bot/`, `jobs/`, `alembic/`, Docker-файлы.

5. TypeScript-версия в `src/` используется ТОЛЬКО как референс поведения. Никакой TS-код ты не запускаешь и не деплоишь. В этом задании TS можешь вообще не трогать.

6. НИКОГДА не логируй реальные значения секретов из `.env`. В логах и ответах указывай только имена переменных и факт их заполненности.

---

## ПУТЬ НА СЕРВЕРЕ: `/opt/sigmatradebot`

Основные файлы:
- `app/services/blacklist_service.py`
- `scripts/validate-env.py`
- `.env`
- `docker-compose.python.yml`
- `Dockerfile.python`
- `docker-entrypoint.sh`

---

## ЦЕЛИ

1. Окончательно устранить проблему с кодировкой `app/services/blacklist_service.py` так, чтобы Python нормально импортировал модуль и не было ошибок Unicode.

2. Настроить корректный запуск скрипта валидации окружения `scripts/validate-env.py` внутри Docker-контейнера.

3. Обеспечить корректную и безопасную настройку `.env` на прод-сервере.

4. Запустить бот, worker и scheduler в production через Docker Compose и убедиться, что:
   - контейнеры в статусе `running/healthy`;
   - в логах нет ошибок `ERROR`, `CRITICAL`, `Traceback`;
   - бот реально работает.

---

## РАБОТАЙ СТРОГО ПО ЭТАПАМ НИЖЕ

---

### ЭТАП 0. ПРОВЕРКА ЛОКАЛЬНОГО PYTHON-КОДА (blacklist_service.py)

**0.1.** В локальном репозитории (в Cursor) открой файл:
- `app/services/blacklist_service.py`

**0.2.** Убедись, что:
- файл сохранён в UTF-8 без BOM;
- в нём НЕТ null-байтов.

**0.3.** В терминале локально запусти:

```bash
cd <корень локального репо>
file app/services/blacklist_service.py
python3 -m py_compile app/services/blacklist_service.py
```

**Требование:**
- `file` должен показывать что-то вроде: `UTF-8 Unicode text`;
- `py_compile` не должен выдавать ошибок.

**0.4.** Если были правки — создай коммит и запушь в основной удалённый репозиторий:

```bash
git status
git add app/services/blacklist_service.py
git commit -m "Fix encoding of blacklist_service.py to UTF-8"
git push
```

Если изменений нет — этот шаг пропусти.

---

### ЭТАП 1. СИНХРОНИЗАЦИЯ КОДА НА СЕРВЕРЕ (GIT + ENCODING)

**1.1.** Подключись к серверу по SSH:

```bash
gcloud compute ssh sigmatrade-20251108-210354 --zone=europe-north1-a --project=telegram-bot-444304
```

**1.2.** Перейди в каталог проекта:

```bash
cd /opt/sigmatradebot
```

**1.3.** Посмотри состояние git:

```bash
git status
git remote -v
git rev-parse --abbrev-ref HEAD
```

**1.4.** Если `app/services/blacklist_service.py` помечен как изменённый и/или есть локальные несохранённые изменения:

* Сначала зафиксируй их в stash, чтобы ничего не потерять:

```bash
git stash push -u -m "server-local-changes-before-sync"
```

**1.5.** Обнови код до последней версии ветки, с которой работаешь (используй ту ветку, которая вернулась в `git rev-parse --abbrev-ref HEAD`, например `main`):

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git fetch origin
git reset --hard origin/$BRANCH
```

**1.6.** Проверь файл кодировкой на сервере:

```bash
file app/services/blacklist_service.py
python3 -c "with open('app/services/blacklist_service.py', 'rb') as f: print('Encoding:', 'UTF-16' if f.read(2) == b'\xff\xfe' else 'UTF-8')"
python3 -m py_compile app/services/blacklist_service.py
```

**Требования:**
- `file` должен показывать UTF-8 текст;
- проверка через `python3 -c` должна вывести `Encoding: UTF-8`;
- `py_compile` должен выполниться без ошибок.

**Если что-то не так — ОСТАНОВИСЬ, не продолжай этапы ниже, пока не добьёшься корректного UTF-8 и успешной компиляции.**

---

### ЭТАП 2. ПЕРЕСБОРКА DOCKER-КОНТЕЙНЕРОВ БЕЗ КЭША

Цель — гарантировать, что в контейнер попадёт исправленный `blacklist_service.py`.

**2.1.** В каталоге `/opt/sigmatradebot` останови текущие контейнеры:

```bash
docker compose -f docker-compose.python.yml down
```

**2.2.** Пересобери образа без кэша:

```bash
docker compose -f docker-compose.python.yml build --no-cache
```

**2.3.** Запусти контейнеры:

```bash
docker compose -f docker-compose.python.yml up -d
```

**2.4.** Проверь, что контейнеры запущены:

```bash
docker compose -f docker-compose.python.yml ps
```

**2.5.** Внутри контейнера `bot` ещё раз проверь файл:

```bash
docker compose -f docker-compose.python.yml exec bot file app/services/blacklist_service.py
docker compose -f docker-compose.python.yml exec bot python3 -m py_compile app/services/blacklist_service.py
```

**Требование:**
- Внутри контейнера — тот же UTF-8 и успешная компиляция.

**Если внутри контейнера всё ещё ошибка кодировки — это означает, что в образ копируется не тот файл или не та директория. В этом случае:**
- проверь `Dockerfile.python` на предмет `COPY` и пути;
- исправь пути так, чтобы в образ копировался актуальный код из `/opt/sigmatradebot`.

---

### ЭТАП 3. НАСТРОЙКА ВАЛИДАЦИИ ОКРУЖЕНИЯ (scripts/validate-env.py)

Цель — скрипт `scripts/validate-env.py` ДОЛЖЕН запускаться внутри контейнера до старта бота и аварийно завершать контейнер при неверном окружении.

**3.1.** На сервере в `/opt/sigmatradebot` убедись, что файл существует:

```bash
ls -l scripts
```

Должен быть файл `scripts/validate-env.py`.

**3.2.** Открой и проверь, что скрипт:
- использует `os.environ` или аналог для проверки переменных;
- возвращает код выхода `0` при успехе и `!=0` при ошибке (через `sys.exit(1)` и т.п.).

**3.3.** Проверь, что в `Dockerfile.python` директория `scripts/` реально копируется в образ:
- в блоке `COPY` должно быть либо `COPY . .`, либо отдельное копирование папки `scripts`.

**3.4.** Проверь, что `.dockerignore` НЕ исключает `scripts/`.

Если папка `scripts` исключена — удали эту строчку/исключение и пересобери образы (повтор ЭТАПА 2).

**3.5.** Открой `docker-entrypoint.sh` и приведи логику валидации к следующей схеме (псевдо-шаблон, приведи к рабочему синтаксису bash без ошибок):

```bash
set -e

# Валидация окружения
if [ -f "scripts/validate-env.py" ]; then
  echo "[ENTRYPOINT] Running environment validation..."
  python3 scripts/validate-env.py
  VALIDATION_EXIT_CODE=$?
  if [ $VALIDATION_EXIT_CODE -ne 0 ]; then
    echo "[ENTRYPOINT] Environment validation FAILED with exit code $VALIDATION_EXIT_CODE"
    exit $VALIDATION_EXIT_CODE
  else
    echo "[ENTRYPOINT] Environment validation PASSED"
  fi
else
  echo "[ENTRYPOINT] Environment validation script NOT FOUND (scripts/validate-env.py). Failing."
  exit 1
fi

# Далее запуск самого процесса бота / воркера
exec "$@"
```

**ВАЖНО:**
- Не использовать `python -m scripts.validate_env`, пока нет пакета с `__init__.py`. Используй прямой запуск: `python3 scripts/validate-env.py`.
- Следи, чтобы `WORKDIR` в Dockerfile.python совпадал с корнем, где лежит `scripts/`.

**3.6.** После правок ЭТАП 2 (build + up) НУЖНО ПОВТОРИТЬ, потому что entrypoint и scripts входят в образ.

---

### ЭТАП 4. НАСТРОЙКА ФАЙЛА .ENV НА ПРОД-СЕРВЕРЕ

Цель — `.env` на сервере должен быть:
- полностью заполнен обязательными переменными;
- НЕ попадать в git;
- не светить значения в логах.

**4.1.** Убедись, что `.env` в `.gitignore`:

```bash
grep -n ".env" .gitignore || echo "WARNING: .env is not in .gitignore"
```

Если `.env` не игнорируется, добавь строку `.env` в `.gitignore` (это изменение можно внести локально и закоммитить).

**4.2.** На сервере в `/opt/sigmatradebot`:
- если файла `.env` ещё нет, создай его по шаблону:

```bash
cp .env.python.example .env
```

**4.3.** Открой `.env` на сервере (удобным редактором или через cat/echo) и ПРОВЕРЬ, что заданы как минимум:
- `TELEGRAM_BOT_TOKEN`
- `WALLET_PRIVATE_KEY`
- `WALLET_ADDRESS`
- `DATABASE_URL`
- `RPC_URL`
- `USDT_CONTRACT_ADDRESS`
- `SYSTEM_WALLET_ADDRESS`
- `ADMIN_TELEGRAM_IDS`
- все остальные переменные, которые отмечены как required в `.env.python.example` и/или в `scripts/validate-env.py`.

**4.4.** НЕ ВЫВОДИ значения этих переменных в лог. В логах при проверке окружения можно писать только:
- "переменная X установлена" или "переменная X отсутствует".

**4.5.** Убедись, что код загрузки окружения в Python (например, `app/config` или `settings`) читает `.env` с сервера. Если используется `python-dotenv` или аналог — проверь, что `.env` читается из корня проекта.

---

### ЭТАП 5. ПОВТОРНАЯ СБОРКА И ЗАПУСК КОНТЕЙНЕРОВ

После исправления:
- кодировки `blacklist_service.py`;
- `docker-entrypoint.sh`;
- `.env`;

нужно полностью перезапустить стек.

**5.1.** На сервере:

```bash
cd /opt/sigmatradebot
docker compose -f docker-compose.python.yml down
docker compose -f docker-compose.python.yml build --no-cache
docker compose -f docker-compose.python.yml up -d
```

**5.2.** Проверка статусов:

```bash
docker compose -f docker-compose.python.yml ps
```

**Ожидается:**
- `bot`, `worker`, `scheduler`, `postgres`, `redis` в статусе `Up`.

**5.3.** Проверка логов:

```bash
docker compose -f docker-compose.python.yml logs bot --tail=100
docker compose -f docker-compose.python.yml logs worker --tail=100
docker compose -f docker-compose.python.yml logs scheduler --tail=100
```

**Требования:**
- нет постоянных сообщений уровня `ERROR`, `CRITICAL`, `Traceback`;
- нет повторяющихся ошибок по импортам и кодировке `blacklist_service.py`;
- нет сообщений о провале валидации окружения.

**Если в логах есть ошибки:**
- выпиши текст ошибки;
- вернись к соответствующему модулю (Python-код, Dockerfile, .env);
- исправь;
- повтори цикл: `build --no-cache` → `up -d` → `logs`.

---

### ЭТАП 6. ФИНАЛЬНАЯ ПРОВЕРКА РАБОТЫ БОТА

**6.1.** Убедись, что Telegram-бот реально запущен и отвечает:
- со своего аккаунта в Telegram напиши команду `/start` боту;
- проверь, что ботовый сценарий начинается без ошибок (нет падений в логах, bot-контейнер не рестартует).

**6.2.** В логах `bot` ещё раз убедись, что:
- нет новых `Traceback`;
- нет ошибок по окружению;
- нет ошибок по импортам, в том числе по `blacklist_service.py`.

**6.3.** Если всё выше выполнено:
- считаем, что:
  - проблема кодировки `blacklist_service.py` устранена;
  - валидация окружения работает и останавливает контейнер при некорректных `.env`;
  - `.env` корректно настроен и защищён;
  - бот успешно работает в production.

---

## ФОРМАТ ОТЧЁТА ДЛЯ ЗАКАЗЧИКА (ЧЕЛОВЕКА)

В конце своей работы выдай структурированный отчёт:

1. Что было сделано по `blacklist_service.py` (локально и на сервере).
2. Как была настроена и проверена валидация окружения (`docker-entrypoint.sh` + `scripts/validate-env.py`).
3. Как проверена корректность `.env` (без вывода реальных значений).
4. Какие команды деплоя были реально выполнены.
5. Состояние контейнеров (`docker compose ps`).
6. Итоговая проверка логов и работы бота.

