from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
                            InlineKeyboardButton)


def main_menu(day_label: str = None, week_label: str = None) -> ReplyKeyboardMarkup:
    buttons = []
    if day_label:
        suffix = f" — {week_label}" if week_label else ""
        buttons.append([KeyboardButton(text=f"▶️ Начать: {day_label}{suffix}")])
    else:
        buttons.append([KeyboardButton(text="💪 Тренировка"), KeyboardButton(text="🍽 Питание")])
    buttons.append([KeyboardButton(text="➕ Записать еду"), KeyboardButton(text="🍴 Что съел сегодня")])
    buttons.append([KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⚙️ Настройки")])
    buttons.append([KeyboardButton(text="📋 Сводка на сегодня"), KeyboardButton(text="📚 Энциклопедия")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def nutrition_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Записать приём пищи")],
            [KeyboardButton(text="🍴 Что съел сегодня")],
            [KeyboardButton(text="📋 Итог за сегодня"), KeyboardButton(text="💡 Совет по питанию")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True
    )


def workout_menu(day_label: str, week_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"▶️ Начать: {day_label}")],
            [KeyboardButton(text="📋 План тренировки"), KeyboardButton(text="📈 Прогресс")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True
    )


def workout_logging_keyboard(exercise: str, set_num: int, total_sets: int,
                               planned_weight: float, reps_range: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⏭ Пропустить подход {set_num}/{total_sets}",
            callback_data=f"skip_set:{set_num}"
        )],
        [
            InlineKeyboardButton(text="📖 Техника", callback_data="technique"),
            InlineKeyboardButton(text="🏁 Завершить", callback_data="finish_workout"),
        ],
    ])


def rest_timer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 мин",  callback_data="rest:60"),
            InlineKeyboardButton(text="1:30",   callback_data="rest:90"),
            InlineKeyboardButton(text="2 мин",  callback_data="rest:120"),
            InlineKeyboardButton(text="2:30",   callback_data="rest:150"),
        ],
        [
            InlineKeyboardButton(text="⏭ Пропустить", callback_data="rest:0"),
            InlineKeyboardButton(text="🏁 Завершить", callback_data="finish_workout"),
        ],
    ])


def finish_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, завершить", callback_data="confirm_finish")],
        [InlineKeyboardButton(text="↩️ Продолжить", callback_data="continue_workout")],
    ])
