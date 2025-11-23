# 🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА БЕЗОПАСНОСТИ - УДАЛЕНИЕ ТОКЕНА ИЗ GIT

## Проблема
Токен бота `8490693145:AAEECwr4c-S-PuHVIccFCw4mMpH0-Uq_rhs` был обнаружен в файле `SERVER_ACCESS.md` в истории Git.

## Что сделано
1. ✅ Токен удален из текущего файла `SERVER_ACCESS.md`
2. ✅ Файл добавлен в `.gitignore`
3. ✅ Создан коммит с удалением токена

## Что нужно сделать СРОЧНО

### Вариант 1: Использовать BFG Repo-Cleaner (РЕКОМЕНДУЕТСЯ)

```bash
# 1. Установить BFG (если не установлен)
# Windows: choco install bfg
# Или скачать: https://rtyley.github.io/bfg-repo-cleaner/

# 2. Клонировать репозиторий как mirror
git clone --mirror https://github.com/Avertenandor/sigmatradebot2.git

# 3. Удалить токен из истории
bfg --replace-text replacements.txt sigmatradebot2.git

# Где replacements.txt содержит:
# 8490693145:AAEECwr4c-S-PuHVIccFCw4mMpH0-Uq_rhs==>YOUR_BOT_TOKEN_HERE

# 4. Очистить и force push
cd sigmatradebot2.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
```

### Вариант 2: Использовать git filter-repo

```bash
# 1. Установить git-filter-repo
pip install git-filter-repo

# 2. Удалить токен из истории
git filter-repo --replace-text replacements.txt

# Где replacements.txt:
# 8490693145:AAEECwr4c-S-PuHVIccFCw4mMpH0-Uq_rhs==>YOUR_BOT_TOKEN_HERE

# 3. Force push
git push origin --force --all
git push origin --force --tags
```

### Вариант 3: Удалить файл из истории (если файл не нужен)

```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch SERVER_ACCESS.md" \
  --prune-empty --tag-name-filter cat -- --all

git push origin --force --all
git push origin --force --tags
```

## ⚠️ ВАЖНО

1. **Force push перезапишет историю** - убедитесь, что все разработчики знают об этом
2. **После force push** все должны сделать:
   ```bash
   git fetch origin
   git reset --hard origin/main
   ```
3. **Токен уже скомпрометирован** - нужно создать новый токен через @BotFather
4. **Проверить другие секреты** - QuickNode API key тоже в файле!

## Проверка

После удаления проверить:
```bash
git log --all -p -S "8490693145"  # Должно вернуть пустой результат
git log --all -p -S "AAEECwr4c"   # Должно вернуть пустой результат
```

## GitHub

Если репозиторий публичный, токен уже виден всем. Нужно:
1. Немедленно создать новый токен
2. Удалить старый токен из истории
3. Обновить токен на сервере

