# API Reference — Fitness Bot

**Версия:** 1.0  
**Дата:** 2026-05-30

Справочник по всем командам, кнопкам, callback_data и FSM-переходам.

---

## 1. Команды бота

| Команда | Handler | Описание |
|---------|---------|---------|
| `/start` | `main_menu.cmd_start` | Главное меню; если новый пользователь — запускает онбординг |
| `/workout` | `main_menu.cmd_workout` | Переход в раздел тренировок |
| `/food` | `main_menu.cmd_food` | Начать запись приёма пищи |
| `/summary` | `main_menu.cmd_summary` | Сводка за сегодня |
| `/stats` | `main_menu.cmd_stats` | Статистика |
| `/settings` | `main_menu.cmd_settings` | Настройки |

---

## 2. Reply-кнопки главного меню

| Текст кнопки | Handler | Описание |
|-------------|---------|---------|
| `💪 Тренировка` | `workout.workout_section` | Меню тренировок |
| `🍽 Питание` | `nutrition.nutrition_section` | Меню питания |
| `➕ Записать еду` | `nutrition.ask_food` | Быстрый вход в запись еды |
| `🍴 Что съел сегодня` | `nutrition.food_detail` | Детальный список приёмов пищи |
| `📊 Статистика` | `stats.show_stats` | Общая статистика |
| `⚙️ Настройки` | `settings.settings_menu` | Меню настроек |
| `📋 Сводка на сегодня` | `stats.today_summary` | Питание + тренировка одним сообщением |
| `📚 Энциклопедия` | `encyclopedia.encyclopedia_start` | Каталог упражнений |
| `▶️ Начать: {день}` | `workout.start_workout` | Быстрый старт тренировки (динамический) |

---

## 3. Reply-кнопки раздела питания

| Текст кнопки | Handler | Описание |
|-------------|---------|---------|
| `➕ Записать приём пищи` | `nutrition.ask_food` | FSM: ожидание ввода еды |
| `🍴 Что съел сегодня` | `nutrition.food_detail` | Список приёмов с КБЖУ и временем |
| `📋 Итог за сегодня` | `nutrition.day_summary` | Краткий итог: список + суммарные КБЖУ |
| `💡 Совет по питанию` | `nutrition.nutrition_tip` | AI-анализ текущего рациона |
| `🏠 Главное меню` | `main_menu.go_main` | Возврат |

---

## 4. Reply-кнопки раздела тренировок

| Текст кнопки | Handler | Описание |
|-------------|---------|---------|
| `▶️ Начать: {день}` | `workout.start_workout` | Начать тренировку |
| `📋 План тренировки` | `workout.show_plan` | Показать план текущего дня |
| `📈 Прогресс` | `workout.show_progress` | Статистика тоннажа |
| `🏠 Главное меню` | `main_menu.go_main` | Возврат |

---

## 5. Inline callback_data

### 5.1 Тренировка

| callback_data | Handler | Описание |
|---------------|---------|---------|
| `skip_set:{n}` | `workout.handle_skip_set` | Пропустить подход №n |
| `technique` | `workout.handle_technique` | Показать технику текущего упражнения |
| `finish_workout` | `workout.handle_finish_request` | Запросить завершение тренировки |
| `confirm_finish` | `workout.handle_confirm_finish` | Подтвердить завершение |
| `continue_workout` | `workout.handle_continue` | Отменить завершение, продолжить |
| `rest:{seconds}` | `workout.handle_rest_timer` | Установить таймер отдыха (60/90/120/150/0) |

### 5.2 Питание

| callback_data | Handler | Описание |
|---------------|---------|---------|
| `log_food` | `nutrition.cb_log_food` | Начать запись еды (из напоминания) |

### 5.3 Энциклопедия

| callback_data | Handler | Описание |
|---------------|---------|---------|
| `enc` | `encyclopedia.cb_categories` | Показать список категорий |
| `ec:{cat_idx}` | `encyclopedia.cb_category` | Показать упражнения категории (0–5) |
| `ee:{cat_idx}:{ex_idx}` | `encyclopedia.cb_exercise` | Показать технику упражнения |

**Индексы категорий:**

| cat_idx | Категория |
|---------|----------|
| 0 | 🏋️ Грудь |
| 1 | 🔙 Спина |
| 2 | 🦵 Ноги |
| 3 | 💪 Плечи |
| 4 | 💪 Руки |
| 5 | 🎯 Пресс и кор |

---

## 6. FSM-состояния и переходы

### 6.1 Онбординг (`handlers/onboarding.py`)

```
Onboarding.age
  → ввод возраста →
Onboarding.weight
  → ввод веса →
Onboarding.height
  → ввод роста →
Onboarding.goal         [inline: mass / cut / maintain]
  → выбор цели →
Onboarding.experience   [inline: beginner / intermediate / advanced]
  → выбор опыта →
Onboarding.days         [inline: 3 / 4 / 5]
  → выбор дней →
Onboarding.equipment    [inline: gym / home / no_equipment]
  → выбор оборудования →
Onboarding.injuries
  → ввод травм / "нет" →
[AI-генерация программы]
→ главное меню
```

### 6.2 Тренировка (`handlers/workout.py`)

```
[главное меню]
  → ▶️ Начать: {день} →
WorkoutLogging.logging_sets
  ├─ ввод "вес×повторения RPEn" → save_set() → следующий подход
  ├─ callback: skip_set:{n}    → пропустить, следующий подход
  ├─ callback: rest:{seconds}  → таймер → следующий подход
  ├─ callback: technique       → техника (не меняет состояние)
  └─ callback: finish_workout  → finish_keyboard()
                                  ├─ confirm_finish → анализ → [Idle]
                                  └─ continue_workout → продолжить
```

### 6.3 Питание (`handlers/nutrition.py`)

```
[меню питания / главное меню]
  → ➕ Записать еду →
FoodLogging.waiting_input
  ├─ текстовое сообщение → parse_food() → log_food() → [Idle]
  ├─ голосовое сообщение → transcribe_voice() → parse_food() → log_food() → [Idle]
  └─ навигационная кнопка → state.clear() → соответствующий handler
```

### 6.4 Настройки (`handlers/settings.py`)

```
[главное меню]
  → ⚙️ Настройки →
  ├─ "вес {число}" → update_user(weight=...) → [Idle]  (из любого места)
  └─ Setup.waiting_weight / Setup.waiting_calories → обновление → [Idle]
```

---

## 7. Сервисные функции AI (`services/ai_service.py`)

### `parse_food(text: str) -> dict`
**Вход:** произвольный текст с едой  
**Выход:** `{"description": str, "calories": float, "protein": float, "carbs": float, "fat": float}`  
**Модель:** llama-3.3-70b-versatile

---

### `get_exercise_technique(exercise: str) -> str`
**Вход:** название упражнения (рус.)  
**Выход:** структурированный текст с разделами:
- 🎯 Ментальный фокус
- ⚙️ Техника выполнения (5 шагов)
- 🚫 Критические ошибки
- ⚠️ Ошибки новичка
- 💪 Правильные ощущения

**Модель:** llama-3.3-70b-versatile  
**Кэш:** `_technique_cache` в `encyclopedia.py` (in-memory)

---

### `analyze_workout(current, previous, program) -> str`
**Вход:** текущая тренировка, предыдущая тренировка того же типа, план  
**Выход:** анализ прогресса, рекомендации на следующую сессию  
**Модель:** llama-3.3-70b-versatile

---

### `transcribe_voice(audio_bytes: bytes, filename: str) -> str`
**Вход:** байты аудиофайла (ogg)  
**Выход:** транскрипция текстом  
**Модель:** Groq Whisper

---

### `get_exercise_gif(exercise_name: str) -> str | None`
**Вход:** английское название упражнения  
**Выход:** URL изображения с wger.de или `None`  
**Процесс:**
1. Groq: перевести на английский
2. `_get_index()` → лениво строит кэш из wger API (264 упражнения)
3. Поиск: точное совпадение → частичное совпадение (подстрока)

---

## 8. Форматы пользовательского ввода

### Подходы в тренировке
```
Формат:  вес×повторения [RPEn]
Примеры: 80x5 RPE8
         100x3 RPE9
         60x10          (RPE = 0 если не указан)
```
Регулярное выражение: `(\d+(?:[.,]\d+)?)[xх×](\d+)(?:\s*RPE\s*(\d+(?:[.,]\d+)?))?`

### Обновление веса
```
Формат:  вес {число}
Примеры: вес 75
         вес 82.5
```
Обрабатывается в `settings.py` через `F.text.regexp(...)` из любого состояния.

### Ввод еды
```
Форматы: 200г куриной грудки, 150г риса, огурец
         творог 5% 200г, банан, кофе с молоком
         [голосовое сообщение]
```
Свободный текст — AI-парсинг через Groq.

---

## 9. Навигационные кнопки (исключения из FSM)

Список кнопок, которые всегда прерывают FSM-состояние `FoodLogging.waiting_input`:

```python
_NAV_BUTTONS = {
    "🏠 Главное меню", "💪 Тренировка", "🍽 Питание",
    "📊 Статистика", "⚙️ Настройки",
    "➕ Записать приём пищи", "➕ Записать еду",
    "📋 Итог за сегодня", "💡 Совет по питанию",
    "🍴 Что съел сегодня",
}
```
