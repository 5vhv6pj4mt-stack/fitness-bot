"""
Редактирование записей питания и подходов тренировок.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import (
    get_food_entry, update_food_entry, delete_food_entry,
    get_food_log_dates, get_day_food_entries,
    get_workout_set, update_workout_set, delete_workout_set,
    recalculate_workout_totals, get_workout_sets, get_recent_workouts,
)
from services.ai_service import parse_food, transcribe_voice
from states.states import EditFood, EditWorkout
from handlers.workout import parse_set_input
from handlers.nav import meal_icon

router = Router()

WEEK_TYPES = {"strength": "Силовая", "volume": "Объёмная", "deload": "Разгрузочная"}
DAY_TYPES = {"upper_strength": "Верх — Сила", "upper_volume": "Верх — Объём", "legs": "Ноги"}

_MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

# Кнопки навигации — при нажатии любой из них сбрасываем FSM
_NAV_BUTTONS = frozenset({
    "🏠 Главное меню", "💪 Тренировка", "🍽 Питание",
    "📊 Статистика", "⚙️ Настройки",
    "✏️ Изменить запись питания", "✏️ Изменить тренировку",
})


def _fmt_date(date_str: str) -> str:
    """'2025-05-28' → '28 мая'"""
    _, m, d = date_str.split("-")
    return f"{int(d)} {_MONTHS[int(m) - 1]}"


def _fmt_w(w: float) -> str:
    """80.0 → '80', 82.5 → '82.5'"""
    return str(int(w)) if w == int(w) else f"{w:g}"



# ═══════════════════════════════════════════════════════
# ПИТАНИЕ — редактирование
# ═══════════════════════════════════════════════════════

def _dates_kb(dates: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for d in dates:
        label = f"📅 {_fmt_date(d['date'])} — {d['count']} зап."
        rows.append([InlineKeyboardButton(text=label, callback_data=f"ef_date:{d['date']}")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="ef_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _entries_kb(entries: list[dict], date: str) -> InlineKeyboardMarkup:
    rows = []
    for e in entries:
        icon = meal_icon(e["created_at"][11:16])
        desc = e["description"].split("\n")[0][:28]
        label = f"{icon} {desc} — {e['calories']:.0f} ккал"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"ef_entry:{e['id']}")])
    rows.append([InlineKeyboardButton(text="← Назад к датам", callback_data="ef_dates")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _entry_actions_kb(entry_id: int, date: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"ef_edit:{entry_id}"),
            InlineKeyboardButton(text="🗑 Удалить",   callback_data=f"ef_del:{entry_id}"),
        ],
        [InlineKeyboardButton(text="← К списку", callback_data=f"ef_date:{date}")],
    ])


@router.message(F.text == "✏️ Изменить запись питания")
async def cmd_edit_food(message: Message, state: FSMContext):
    await state.clear()
    dates = await get_food_log_dates(message.from_user.id)
    if not dates:
        await message.answer("📭 Нет записей питания.")
        return
    await message.answer("📅 Выбери дату:", reply_markup=_dates_kb(dates))


@router.callback_query(F.data == "ef_dates")
async def cb_ef_dates(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    dates = await get_food_log_dates(callback.from_user.id)
    if not dates:
        await callback.message.edit_text("📭 Нет записей питания.")
        return
    await callback.message.edit_text("📅 Выбери дату:", reply_markup=_dates_kb(dates))
    await callback.answer()


@router.callback_query(F.data.startswith("ef_date:"))
async def cb_ef_date(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    date = callback.data[8:]
    entries = await get_day_food_entries(callback.from_user.id, date)
    if not entries:
        await callback.answer("За этот день записей нет")
        return
    await callback.message.edit_text(
        f"🍴 <b>Записи за {_fmt_date(date)}</b>\nВыбери запись:",
        reply_markup=_entries_kb(entries, date),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ef_entry:"))
async def cb_ef_entry(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    entry_id = int(callback.data[9:])
    entry = await get_food_entry(entry_id)
    if not entry:
        await callback.answer("Запись не найдена")
        return
    time = entry["created_at"][11:16]
    text = (
        f"{meal_icon(time)} <b>{entry['description']}</b>\n"
        f"🕐 {time}\n"
        f"🔥 {entry['calories']:.0f} ккал  ·  "
        f"Б {entry['protein']:.0f}г  У {entry['carbs']:.0f}г  Ж {entry['fat']:.0f}г"
    )
    await callback.message.edit_text(
        text,
        reply_markup=_entry_actions_kb(entry_id, entry["date"]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ef_edit:"))
async def cb_ef_edit(callback: CallbackQuery, state: FSMContext):
    entry_id = int(callback.data[8:])
    entry = await get_food_entry(entry_id)
    if not entry:
        await callback.answer("Запись не найдена")
        return
    await state.set_state(EditFood.editing_entry)
    await state.update_data(entry_id=entry_id, entry_date=entry["date"])
    await callback.message.edit_text(
        f"✏️ Редактируем:\n<b>{entry['description']}</b>\n\n"
        "Введи что съел (текст или голосовое):\n"
        "<i>Пример: 200г куриной грудки, 150г риса</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"ef_entry:{entry_id}")
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ef_del:"))
async def cb_ef_del(callback: CallbackQuery):
    entry_id = int(callback.data[7:])
    entry = await get_food_entry(entry_id)
    if not entry:
        await callback.answer("Запись не найдена")
        return
    await callback.message.edit_text(
        f"🗑 Удалить запись?\n\n<b>{entry['description']}</b>\n{entry['calories']:.0f} ккал",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да, удалить",  callback_data=f"ef_confirm:{entry_id}"),
            InlineKeyboardButton(text="❌ Нет",          callback_data=f"ef_entry:{entry_id}"),
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ef_confirm:"))
async def cb_ef_confirm(callback: CallbackQuery):
    entry_id = int(callback.data[11:])
    entry = await get_food_entry(entry_id)
    if not entry:
        await callback.answer("Уже удалено")
        return
    date = entry["date"]
    await delete_food_entry(entry_id)

    entries = await get_day_food_entries(callback.from_user.id, date)
    if not entries:
        await callback.message.edit_text(
            f"✅ Удалено. За {_fmt_date(date)} больше нет записей.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← К датам", callback_data="ef_dates")
            ]]),
        )
    else:
        await callback.message.edit_text(
            f"✅ Удалено.\n\n🍴 <b>Записи за {_fmt_date(date)}:</b>",
            reply_markup=_entries_kb(entries, date),
            parse_mode="HTML",
        )
    await callback.answer("Удалено")


@router.callback_query(F.data == "ef_cancel")
async def cb_ef_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


# FSM: ввод нового описания еды

async def _save_edited_food(message: Message, state: FSMContext, food_text: str, status_msg):
    data = await state.get_data()
    entry_id = data["entry_id"]
    entry_date = data["entry_date"]
    await state.clear()
    try:
        result = await parse_food(food_text)
        await update_food_entry(
            entry_id,
            result.get("description", food_text[:300]),
            result["calories"], result["protein"], result["carbs"], result["fat"],
        )
        await status_msg.edit_text(
            f"✅ <b>Обновлено:</b> {result.get('description')}\n"
            f"🔥 {result['calories']:.0f} ккал  ·  "
            f"Б {result['protein']:.0f}г  У {result['carbs']:.0f}г  Ж {result['fat']:.0f}г",
            parse_mode="HTML",
        )
        entries = await get_day_food_entries(message.from_user.id, entry_date)
        await message.answer(
            f"🍴 <b>Обновлённый список за {_fmt_date(entry_date)}:</b>",
            reply_markup=_entries_kb(entries, entry_date),
            parse_mode="HTML",
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Не удалось распознать. Попробуй написать подробнее.\n<i>{e}</i>",
            parse_mode="HTML",
        )


@router.message(EditFood.editing_entry, F.text, ~F.text.in_(_NAV_BUTTONS), ~F.text.startswith("/"))
async def handle_edit_food_text(message: Message, state: FSMContext):
    msg = await message.answer("⏳ Считаю КБЖУ...")
    await _save_edited_food(message, state, message.text, msg)


@router.message(EditFood.editing_entry, F.voice)
async def handle_edit_food_voice(message: Message, state: FSMContext):
    msg = await message.answer("🎤 Распознаю голос...")
    try:
        file = await message.bot.get_file(message.voice.file_id)
        audio = await message.bot.download_file(file.file_path)
        text = await transcribe_voice(audio.read(), "voice.ogg")
        await msg.edit_text(f"🎤 <i>{text}</i>\n\n⏳ Считаю КБЖУ...", parse_mode="HTML")
        await _save_edited_food(message, state, text, msg)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}", parse_mode="HTML")
        await state.clear()


# ═══════════════════════════════════════════════════════
# ТРЕНИРОВКИ — редактирование
# ═══════════════════════════════════════════════════════

def _workouts_kb(workouts: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for w in workouts:
        day = DAY_TYPES.get(w["day_type"], w["day_type"])
        week = WEEK_TYPES.get(w["week_type"], w.get("week_type", ""))
        status = "" if w["is_finished"] else " ⏳"
        label = f"💪 {_fmt_date(w['date'])} — {day} ({week}){status}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"ew_sel:{w['id']}")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="ew_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _sets_view(sets: list[dict], workout_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Список подходов: текст + инлайн-кнопки."""
    # Группируем по упражнению (сохраняем порядок)
    exercises: dict[str, list[dict]] = {}
    for s in sets:
        exercises.setdefault(s["exercise"], []).append(s)

    lines = ["<b>Выбери подход для редактирования:</b>\n"]
    rows = []
    for ex, ex_sets in exercises.items():
        lines.append(f"<b>{ex}:</b>")
        for s in ex_sets:
            w, r, rpe = _fmt_w(s["actual_weight"]), s["reps"], s["rpe"]
            lines.append(f"  п.{s['set_number']}: {w}кг × {r} · RPE {rpe:g}")
            label = f"{ex[:18]} · п.{s['set_number']}: {w}×{r} RPE{rpe:g}"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"ew_set:{s['id']}")])

    rows.append([InlineKeyboardButton(text="← К тренировкам", callback_data="ew_back")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _set_actions_kb(set_id: int, workout_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"ew_edit:{set_id}"),
            InlineKeyboardButton(text="🗑 Удалить",   callback_data=f"ew_del:{set_id}"),
        ],
        [InlineKeyboardButton(text="← К подходам", callback_data=f"ew_sel:{workout_id}")],
    ])


@router.message(F.text == "✏️ Изменить тренировку")
async def cmd_edit_workout(message: Message, state: FSMContext):
    await state.clear()
    workouts = await get_recent_workouts(message.from_user.id)
    if not workouts:
        await message.answer("📭 Нет тренировок для редактирования.")
        return
    await message.answer("💪 Выбери тренировку:", reply_markup=_workouts_kb(workouts))


@router.callback_query(F.data == "ew_back")
async def cb_ew_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    workouts = await get_recent_workouts(callback.from_user.id)
    if not workouts:
        await callback.message.edit_text("📭 Нет тренировок.")
        return
    await callback.message.edit_text("💪 Выбери тренировку:", reply_markup=_workouts_kb(workouts))
    await callback.answer()


@router.callback_query(F.data.startswith("ew_sel:"))
async def cb_ew_sel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    workout_id = int(callback.data[7:])
    sets = await get_workout_sets(workout_id)
    if not sets:
        await callback.answer("В этой тренировке нет подходов")
        return
    text, kb = _sets_view(sets, workout_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ew_set:"))
async def cb_ew_set(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    set_id = int(callback.data[7:])
    s = await get_workout_set(set_id)
    if not s:
        await callback.answer("Подход не найден")
        return
    w = _fmt_w(s["actual_weight"])
    text = (
        f"⚡ <b>{s['exercise']}</b>\n"
        f"Подход {s['set_number']}: {w}кг × {s['reps']} повт. · RPE {s['rpe']:g}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=_set_actions_kb(set_id, s["workout_id"]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ew_edit:"))
async def cb_ew_edit(callback: CallbackQuery, state: FSMContext):
    set_id = int(callback.data[8:])
    s = await get_workout_set(set_id)
    if not s:
        await callback.answer("Подход не найден")
        return
    await state.set_state(EditWorkout.editing_set)
    await state.update_data(set_id=set_id, workout_id=s["workout_id"])
    w = _fmt_w(s["actual_weight"])
    await callback.message.edit_text(
        f"✏️ <b>{s['exercise']}</b> — подход {s['set_number']}\n"
        f"Сейчас: {w}кг × {s['reps']} · RPE {s['rpe']:g}\n\n"
        "Введи новые значения:\n"
        "<code>вес × повторения RPE</code>\n"
        "<i>Пример: 85x6 RPE8  или  85 6 8</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"ew_set:{set_id}")
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ew_del:"))
async def cb_ew_del(callback: CallbackQuery):
    set_id = int(callback.data[7:])
    s = await get_workout_set(set_id)
    if not s:
        await callback.answer("Подход не найден")
        return
    w = _fmt_w(s["actual_weight"])
    await callback.message.edit_text(
        f"🗑 Удалить подход?\n\n<b>{s['exercise']}</b>\n"
        f"п.{s['set_number']}: {w}кг × {s['reps']} · RPE {s['rpe']:g}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да, удалить",  callback_data=f"ew_confirm:{set_id}"),
            InlineKeyboardButton(text="❌ Нет",          callback_data=f"ew_set:{set_id}"),
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ew_confirm:"))
async def cb_ew_confirm(callback: CallbackQuery):
    set_id = int(callback.data[11:])
    s = await get_workout_set(set_id)
    if not s:
        await callback.answer("Уже удалено")
        return
    workout_id = s["workout_id"]
    await delete_workout_set(set_id)
    await recalculate_workout_totals(workout_id)

    sets = await get_workout_sets(workout_id)
    if not sets:
        await callback.message.edit_text(
            "✅ Подход удалён.\n\n📭 В этой тренировке больше нет подходов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← К тренировкам", callback_data="ew_back")
            ]]),
        )
    else:
        text, kb = _sets_view(sets, workout_id)
        await callback.message.edit_text(
            f"✅ Подход удалён.\n\n{text}", reply_markup=kb, parse_mode="HTML"
        )
    await callback.answer("Удалено")


@router.callback_query(F.data == "ew_cancel")
async def cb_ew_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


# FSM: ввод новых значений подхода

@router.message(EditWorkout.editing_set, F.text, ~F.text.in_(_NAV_BUTTONS), ~F.text.startswith("/"))
async def handle_edit_set_text(message: Message, state: FSMContext):
    parsed = parse_set_input(message.text)
    if not parsed:
        await message.answer(
            "❌ Не понял формат. Введи как: <code>85x6 RPE8</code> или <code>85 6 8</code>",
            parse_mode="HTML",
        )
        return

    weight, reps, rpe, _ = parsed
    if rpe is None:
        rpe = 7.0

    data = await state.get_data()
    set_id = data["set_id"]
    workout_id = data["workout_id"]
    await state.clear()

    await update_workout_set(set_id, weight, reps, rpe)
    await recalculate_workout_totals(workout_id)

    await message.answer(
        f"✅ Подход обновлён: {_fmt_w(weight)}кг × {reps} · RPE {rpe:g}"
    )
    sets = await get_workout_sets(workout_id)
    text, kb = _sets_view(sets, workout_id)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
