# Sisyphus 1.0.0

Минималистичный терминальный органайзер для разгрузки мозга.

Заметки, задачи и финансы в одном чистом CLI. С поддержкой Telegram-бота для уведомлений.

## Установка и запуск

```bash
pip install -r requirements.txt
python -m sisyphus
```

Или:

```bash
python launch.py
```

## Настройка Telegram-бота и рассылки

В CLI:

- `/bot token <токен>` — задать токен бота (бот автоматически запустится в фоне при следующем старте программы)
- `/notify daily 09:00` — ежедневная рассылка
- `/notify weekdays 09:00` — по будням
- `/notify weekly mon 09:00` — еженедельно
- `/notify-` — отключить рассылку
- `/forcenotify` — принудительная рассылка прямо сейчас

Бот отвечает только на `/my` (твои задачи по всем проектам).

## Основные команды

- `текст` — заметка
- `@user текст` — задача
- `+100 текст` / `-50 текст` — финансы
- Enter — показать список
- `/del N` — удалить
- `/done N` — отметить выполненным
- `/e N текст` — редактировать
- `/u` / `/r` — undo / redo
- `/fin` — список финансов
- `/export` — экспорт в .xlsx (3 листа)
- `/m` — проекты
- `/h` — справка
- `/q` — выход

## Тесты

```bash
python -m sisyphus --test
```

## Структура проекта

```
sisyphus/
├── core/      # данные, логика, нумерация
├── cli/       # REPL, команды, autocomplete
├── bot/       # Telegram-бот и планировщик
├── tests/
launch.py
requirements.txt
```

## Cross-platform

Pure Python (pathlib). Data in ~/Documents/Sisyphus (or fallback). Same on macOS/Linux/Windows.

## Philosophy

Всё по nakedlunch: ничего лишнего, просто, без заеба, один источник правды (нумерация и данные в core). No extra text on startup. Bare header.

## License

Personal use only. Your data stay yours. See LICENSE.