# Fitness Bot — @stat_sila_bot

Telegram-бот для трекинга тренировок и питания с AI-анализом.

**Путь:** `/home/oracle/fitness-bot/`
**Бот:** `@stat_sila_bot`
**Python:** 3.12 + aiogram 3 + aiosqlite
**AI:** Groq API (llama-3.3-70b-versatile) — `services/ai_service.py`
**БД:** SQLite (`fitness.db`)

## Запуск

```bash
cd /home/oracle/fitness-bot

# Проверить работает ли бот
pgrep -fa "python bot.py"

# Запустить бот
nohup venv/bin/python bot.py >> bot.log 2>&1 &

# Логи
tail -f bot.log
```

## Структура файлов

```
fitness-bot/
├── bot.py                      — точка входа, регистрация роутеров
├── config.py                   — .env (BOT_TOKEN, GROQ_API_KEY, DB_PATH)
├── database/
│   ├── db.py                   — все SQL операции (users, workouts, food_log, user_program)
│   └── program_data.py         — шаблоны программ тренировок
├── handlers/
│   ├── main_menu.py            — /start, главное меню
│   ├── onboarding.py           — FSM онбординг (имя, вес, цель, опыт)
│   ├── workout.py              — тренировки, логирование подходов, таймер отдыха
│   ├── nutrition.py            — питание, голосовой ввод еды, КБЖУ
│   ├── stats.py                — статистика (тоннаж, питание)
│   ├── settings.py             — настройки пользователя, обновление веса
│   └── nav.py                  — хелпер send_nav (единый стиль навигации)
├── keyboards/keyboards.py      — все клавиатуры (main_menu, workout_menu, nutrition_menu и др.)
├── services/
│   ├── ai_service.py           — Groq: parse_food, analyze_workout, get_exercise_technique, transcribe_voice
│   └── scheduler.py            — APScheduler: напоминания о приёмах пищи
├── states/states.py            — FSM состояния (WorkoutLogging, FoodLogging, Setup)
└── venv/                       — виртуальное окружение
```

## База данных — таблицы

| Таблица | Назначение |
|---------|-----------|
| `users` | профиль, цели по КБЖУ, текущая неделя/день программы |
| `user_program` | упражнения по (user_id, week_type, day_type) |
| `workouts` | сессии тренировок, тоннаж, RPE, is_finished, ex_index/set_index |
| `workout_sets` | отдельные подходы (вес, повторы, RPE, заметки) |
| `food_log` | приёмы пищи по датам (КБЖУ) |

## Типы недель и дней

```python
WEEK_TYPES = {"strength": "Силовая", "volume": "Объёмная", "deload": "Разгрузочная"}
DAY_TYPES  = {"upper_strength": "Верх — Сила", "upper_volume": "Верх — Объём", "legs": "Ноги"}
```

## Что реализовано

- [x] Онбординг (имя, вес, рост, возраст, цель, опыт, дни в неделю)
- [x] AI-генерация программы тренировок через Groq
- [x] Логирование подходов с FSM (формат: `50x8 RPE8`)
- [x] Таймер отдыха с обратным отсчётом и уведомлением за 10 сек
- [x] Возобновление незавершённой тренировки
- [x] AI-анализ тренировки после завершения (сравнение с прошлой)
- [x] Трекинг питания — текст или голос → Groq → КБЖУ
- [x] Напоминания о приёмах пищи (APScheduler)
- [x] Статистика: тоннаж, питание, прогресс
- [x] Настройки: вес командой `вес 75`, /start для перестройки программы

## Что можно улучшить / продолжить

- [ ] Графики прогресса (matplotlib → картинка в боте)
- [ ] Редактирование/удаление последнего приёма пищи
- [ ] Ручная корректировка веса в упражнении (прогрессия нагрузки)
- [ ] Недельный отчёт по питанию и тренировкам
- [ ] Команда `/reset` для сброса программы без полного онбординга
- [ ] Systemd-юниты для автозапуска при перезагрузке VPS
