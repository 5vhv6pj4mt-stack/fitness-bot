from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
                            InlineKeyboardButton)


def _fw(w: float) -> str:
    return str(int(w)) if w == int(w) else str(w)


def _fr(r: float) -> str:
    return str(int(r)) if r == int(r) else f"{r:.1f}"


def main_menu(day_label: str = None, week_label: str = None) -> ReplyKeyboardMarkup:
    buttons = []
    if day_label:
        suffix = f" — {week_label}" if week_label else ""
        buttons.append([KeyboardButton(text=f"▶️ Начать: {day_label}{suffix}")])
    buttons.append([KeyboardButton(text="💪 Тренировка"), KeyboardButton(text="🍽 Питание")])
    buttons.append([KeyboardButton(text="➕ Записать еду"), KeyboardButton(text="🍴 Что съел сегодня")])
    buttons.append([KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⚙️ Настройки")])
    buttons.append([KeyboardButton(text="📋 Сводка на сегодня")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)



def nutrition_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Записать приём пищи")],
            [KeyboardButton(text="📌 Шаблоны"), KeyboardButton(text="🍴 Что съел сегодня")],
            [KeyboardButton(text="🤖 Спросить ИИ"), KeyboardButton(text="💡 Совет по питанию")],
            [KeyboardButton(text="✏️ Изменить запись питания")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True
    )


def workout_menu(day_label: str, week_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"▶️ Начать: {day_label}")],
            [KeyboardButton(text="📋 План тренировки"), KeyboardButton(text="📈 Прогресс")],
            [KeyboardButton(text="✏️ Изменить тренировку")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True
    )


def workout_logging_keyboard(exercise: str, set_num: int, total_sets: int,
                               planned_weight: float, reps_range: str) -> InlineKeyboardMarkup:
    rows = []
    top = [InlineKeyboardButton(text="📖 Техника", callback_data="technique")]
    if set_num == 1 and planned_weight > 0:
        top.insert(0, InlineKeyboardButton(text="🔥 Разминка", callback_data="show_warmup"))
    top.append(InlineKeyboardButton(text="🏁 Завершить", callback_data="finish_workout"))
    rows.append(top)
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="workout_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def exercise_prompt_hint(plan_weight: float) -> str:
    """Возвращает текст подсказки под полем ввода подхода.

    Включает hint об изменении веса текстовыми командами, если упражнение
    предполагает вес (plan_weight > 0).
    """
    hint = "Введите результат подхода или воспользуйтесь кнопками ниже."
    if plan_weight > 0:
        hint += "\n💡 Изменить вес: +2.5 / -5 / вес 80"
    return hint


def _fmt_rest(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}" if s else f"{m} мин"


def set_input_keyboard(
    cur_weight: float, cur_reps: int, cur_rpe: float,
    plan_weight: float, cur_rest: int = 0, show_warmup: bool = False,
) -> InlineKeyboardMarkup:
    """Inline-клавиатура для ввода подхода: вес±, повторы±, RPE, отдых±, подтвердить."""
    rows = []

    if plan_weight > 0:
        rows.append([
            InlineKeyboardButton(text="−2.5", callback_data="sw:-"),
            InlineKeyboardButton(text=f"⚖️  {_fw(cur_weight)} кг", callback_data="noop"),
            InlineKeyboardButton(text="+2.5", callback_data="sw:+"),
        ])

    rows.append([
        InlineKeyboardButton(text="−1", callback_data="sr:-"),
        InlineKeyboardButton(text=f"🔁  {cur_reps} повт", callback_data="noop"),
        InlineKeyboardButton(text="+1", callback_data="sr:+"),
    ])

    rpe_vals = [7.0, 7.5, 8.0, 8.5, 9.0]
    rows.append([
        InlineKeyboardButton(
            text=f"✓{_fr(r)}" if abs(r - cur_rpe) < 0.01 else _fr(r),
            callback_data=f"rpe:{r}",
        )
        for r in rpe_vals
    ])

    if cur_rest > 0:
        rows.append([
            InlineKeyboardButton(text="−30", callback_data="rest_adj:-"),
            InlineKeyboardButton(text=f"⏱  {_fmt_rest(cur_rest)}", callback_data="noop"),
            InlineKeyboardButton(text="+30", callback_data="rest_adj:+"),
        ])

    w_part = f"{_fw(cur_weight)}кг × " if plan_weight > 0 else ""
    rest_part = f"  ·  ⏱ {_fmt_rest(cur_rest)}" if cur_rest > 0 else ""
    rows.append([InlineKeyboardButton(
        text=f"✅  {w_part}{cur_reps} повт  RPE {_fr(cur_rpe)}{rest_part}",
        callback_data="confirm_set",
    )])

    tools = []
    if show_warmup:
        tools.append(InlineKeyboardButton(text="🔥 Разминка", callback_data="show_warmup"))
    tools += [
        InlineKeyboardButton(text="📖 Техника", callback_data="technique"),
        InlineKeyboardButton(text="🏁 Завершить", callback_data="finish_workout"),
    ]
    rows.append(tools)
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="workout_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def next_set_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Следующий подход", callback_data="next_set"),
    ]])


def rest_timer_keyboard() -> InlineKeyboardMarkup:
    return rest_input_keyboard(90)


def rest_input_keyboard(seconds: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора времени отдыха с рекомендованным значением и кнопками ±30 сек."""
    m, s = divmod(seconds, 60)
    time_str = f"{m}:{s:02d}" if s else f"{m} мин"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="−30 сек", callback_data="rest_adj:-"),
            InlineKeyboardButton(text=f"⏱  {time_str}", callback_data="noop"),
            InlineKeyboardButton(text="+30 сек", callback_data="rest_adj:+"),
        ],
        [InlineKeyboardButton(text=f"▶️  Начать отдых  {time_str}", callback_data=f"rest:{seconds}")],
        [
            InlineKeyboardButton(text="⏭ Пропустить", callback_data="rest:0"),
            InlineKeyboardButton(text="🏁 Завершить",  callback_data="finish_workout"),
        ],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="workout_to_main")],
    ])


def finish_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, завершить", callback_data="confirm_finish")],
        [InlineKeyboardButton(text="↩️ Продолжить", callback_data="continue_workout")],
    ])