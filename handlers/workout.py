import re
import asyncio
from datetime import date
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import (get_user, update_user, create_workout, save_set,
                          finish_workout, get_last_workout_by_day, get_workout_sets,
                          get_user_program, get_user_day_types, get_user_week_types,
                          update_workout_progress, get_active_workout, discard_all_active_workouts,
                          update_exercise_weight, delete_workout_set)
from keyboards.keyboards import (main_menu, workout_menu, workout_logging_keyboard,
                                  finish_keyboard, rest_timer_keyboard, rest_input_keyboard,
                                  set_input_keyboard, next_set_keyboard)
from services.ai_service import analyze_workout, get_exercise_technique, get_exercise_gif
from states.states import WorkoutLogging
from handlers.nav import send_nav, track_msg

router = Router()

# Хранилище активных таймеров отдыха: chat_id → asyncio.Task
_rest_timers: dict[int, asyncio.Task] = {}


def _cancel_rest_timer(chat_id: int):
    task = _rest_timers.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


async def _try_delete(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def _rest_timer_task(bot: Bot, chat_id: int, seconds: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    WARN_BEFORE = 10
    TICK = 10  # обновлять сообщение каждые N секунд

    def _fmt(s: int) -> str:
        m, sc = divmod(s, 60)
        return f"{m}:{sc:02d}"

    try:
        # Отправляем стартовое сообщение с таймером
        timer_msg = await bot.send_message(
            chat_id,
            f"⏱ Осталось: <b>{_fmt(seconds)}</b>",
            parse_mode="HTML"
        )

        elapsed = 0
        while elapsed < seconds - WARN_BEFORE:
            await asyncio.sleep(TICK)
            elapsed += TICK
            remaining = seconds - elapsed
            if remaining <= WARN_BEFORE:
                break
            try:
                await timer_msg.edit_text(
                    f"⏱ Осталось: <b>{_fmt(remaining)}</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # Предупреждение за 10 сек с кнопкой
        try:
            await timer_msg.edit_text(
                f"⚡️ <b>Осталось {WARN_BEFORE} секунд!</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Готов, начинаю подход", callback_data="rest_ready")
                ]])
            )
        except Exception:
            pass

        await asyncio.sleep(WARN_BEFORE)

        # Время вышло — новое сообщение чтобы пришло уведомление
        try:
            await timer_msg.delete()
        except Exception:
            pass
        try:
            await bot.send_message(
                chat_id, "⏰ <b>Время вышло! Следующий подход 💪</b>",
                parse_mode="HTML", reply_markup=next_set_keyboard()
            )
        except Exception:
            pass

    except asyncio.CancelledError:
        try:
            await timer_msg.edit_text("✅ <b>Подход начат!</b>", parse_mode="HTML", reply_markup=None)
        except Exception:
            pass
    finally:
        _rest_timers.pop(chat_id, None)

DAY_TYPES = {
    "upper_strength": "Верх — Сила",
    "upper_volume": "Верх — Объём",
    "legs": "Ноги",
}
WEEK_TYPES = {
    "strength": "Силовая",
    "volume": "Объёмная",
    "deload": "Разгрузочная",
}


def today() -> str:
    return date.today().isoformat()


def format_plan(exercises: list[dict], week_type: str) -> str:
    lines = []
    for i, ex in enumerate(exercises, 1):
        w = f"{ex['weight']}кг" if ex['weight'] > 0 else "свой вес"
        lines.append(f"{i}. <b>{ex['exercise']}</b> — {ex['sets']}×{ex['reps_range']} @ {w}, RPE {ex['rpe_range']} | отдых {ex['rest']}")
    return "\n".join(lines)


def _fmt_weight(w: float) -> str:
    return str(int(w)) if w == int(w) else str(w)


PROGRESSION_STEP = 2.5


def _parse_reps_default(reps_range: str) -> int:
    """'12-15' → 12, '5' → 5, '30-60 секунд' → 30"""
    nums = re.findall(r'\d+', reps_range)
    return int(nums[0]) if nums else 8


def _parse_rpe_default(rpe_range: str) -> float:
    """'7-9' → 8.0, '8' → 8.0"""
    nums = re.findall(r'\d+(?:\.\d+)?', rpe_range)
    if not nums:
        return 8.0
    if len(nums) == 1:
        return float(nums[0])
    mid = (float(nums[0]) + float(nums[-1])) / 2
    return round(mid * 2) / 2  # округляем до 0.5


def _parse_rest_seconds(rest_str: str) -> int:
    """Парсит строку отдыха в секунды.
    Форматы: '2м30с', '2м', '90с', '2.5 мин', '60-90 сек', '2-3 мин', '1:30'
    При диапазоне берём верхнюю границу (лучше больше отдохнуть).
    """
    s = rest_str.lower().strip()

    # 'XмYс' / 'Xм Yс' — например '2м30с'
    m = re.match(r'(\d+)\s*м\s*(\d+)\s*с', s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))

    # 'X:Y' — например '2:30'
    m = re.match(r'(\d+):(\d{2})', s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))

    # Минуты: 'Xм', 'X мин', 'X-Y мин'
    if re.search(r'м(?:ин)?', s):
        nums = re.findall(r'\d+(?:\.\d+)?', s)
        if not nums:
            return 90
        vals = [round(float(n) * 60) for n in nums]
        return max(30, round(max(vals) / 30) * 30)

    # Секунды: 'Xс', 'X сек', 'X-Y сек', просто число
    nums = re.findall(r'\d+', s)
    if not nums:
        return 90
    vals = [int(n) for n in nums]
    return max(30, round(max(vals) / 30) * 30)


def _init_set_defaults(ex: dict) -> tuple[float, int, float]:
    """Возвращает (weight, reps, rpe) по умолчанию из плана."""
    return ex["weight"], _parse_reps_default(ex["reps_range"]), _parse_rpe_default(ex["rpe_range"])


def _build_set_prompt(data: dict) -> tuple[str, "InlineKeyboardMarkup"]:
    """Строит текст и клавиатуру для ввода текущего подхода."""
    exercises = data["exercises"]
    ex_index = data["ex_index"]
    set_index = data["set_index"]
    all_sets = data["all_sets"]
    cur_w = data.get("current_weight", 0.0)
    cur_r = data.get("current_reps", 8)
    cur_rpe = data.get("current_rpe", 8.0)

    ex = exercises[ex_index]
    table = format_exercise_table(ex, all_sets, set_index)
    text = (
        f"<b>{ex_index + 1}. {ex['exercise']}</b>  ·  RPE {ex['rpe_range']}  ·  отдых {ex['rest']}\n\n"
        + table
        + f"\n\n<b>Подход {set_index + 1}/{ex['sets']}</b>"
    )
    show_warmup = set_index == 0 and ex["weight"] > 0
    is_last_set = set_index == ex["sets"] - 1
    cur_rest = 0 if is_last_set else data.get("current_rest", 0)
    kb = set_input_keyboard(cur_w, cur_r, cur_rpe, ex["weight"], cur_rest, show_warmup)
    return text, kb

_WARMUP_SCHEMES = {
    "strength": [(0.40, 8), (0.60, 5), (0.75, 3), (0.85, 1)],
    "volume":   [(0.50, 10), (0.70, 6), (0.85, 3)],
    "deload":   [(0.50, 10), (0.65, 8)],
}


def format_warmup(exercise: str, work_weight: float, week_type: str) -> str:
    scheme = _WARMUP_SCHEMES.get(week_type, _WARMUP_SCHEMES["volume"])
    lines = [f"🔥 <b>Разминка — {exercise}</b>\n<i>Рабочий вес: {_fmt_weight(work_weight)}кг</i>\n"]
    for pct, reps in scheme:
        raw = work_weight * pct
        rounded = round(raw / 2.5) * 2.5  # до ближайших 2.5кг
        bar = "░" * int(pct * 10)
        lines.append(f"  {int(pct*100)}%  →  <b>{_fmt_weight(rounded)}кг × {reps}</b>  <code>{bar}</code>")
    lines.append("\n▶️ После разминки вводи рабочие подходы как обычно")
    return "\n".join(lines)

def _calculate_progression(all_sets: list[dict], exercises: list[dict]) -> list[dict]:
    """RPE avg ≤ 8.0 → +2.5кг, 8.0–9.0 → держим, >9.0 → -2.5кг. Свой вес пропускаем."""
    result = []
    for ex in exercises:
        if ex["weight"] <= 0:
            continue
        ex_sets = [s for s in all_sets if s["exercise"] == ex["exercise"]]
        if not ex_sets:
            continue
        avg_rpe = sum(s["rpe"] for s in ex_sets) / len(ex_sets)
        old_w = ex["weight"]
        if avg_rpe <= 8.0:
            new_w = old_w + PROGRESSION_STEP
            icon = "↗"
        elif avg_rpe <= 9.0:
            new_w = old_w
            icon = "—"
        else:
            new_w = max(old_w - PROGRESSION_STEP, PROGRESSION_STEP)
            icon = "↘"
        result.append({
            "exercise": ex["exercise"],
            "old_weight": old_w,
            "new_weight": new_w,
            "avg_rpe": avg_rpe,
            "icon": icon,
        })
    return result


def format_exercise_table(ex: dict, all_sets: list, current_set_idx: int) -> str:
    """Таблица подходов: план + выполненные + текущий."""
    logged = [s for s in all_sets if s['exercise'] == ex['exercise']]

    ew = ex['weight']
    w_str = f"{_fmt_weight(ew)}кг" if ew > 0 else "св.в."
    plan_tmpl = f"{w_str}×{ex['reps_range']}"

    rows = []
    for i in range(ex['sets']):
        marker = ">" if i == current_set_idx else " "
        plan = f"{plan_tmpl:<13}"

        if i < len(logged):
            s = logged[i]
            aw_s = _fmt_weight(s['actual_weight'])
            rpe_s = _fmt_weight(s['rpe'])
            fact = f"[+] {aw_s}x{s['reps']} R{rpe_s}"
        elif i == current_set_idx:
            fact = "[>] ввести"
        else:
            fact = "[ ] ..."

        rows.append(f"{marker}{i + 1}. {plan} {fact}")

    return "<code>" + "\n".join(rows) + "</code>"


async def get_current_day(user: dict) -> tuple[str, str, list[dict]]:
    """Возвращает (day_type, week_type, exercises) для текущей тренировки пользователя."""
    week_type = user["current_week_type"]
    day_index = user["current_day_index"]
    day_types = await get_user_day_types(user["user_id"], week_type)
    if not day_types:
        return "", week_type, []
    day_type = day_types[day_index % len(day_types)]
    exercises = await get_user_program(user["user_id"], week_type, day_type)
    return day_type, week_type, exercises


@router.message(F.text == "💪 Тренировка")
async def workout_section(message: Message, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    user = await get_user(message.from_user.id)

    # Проверяем незавершённую тренировку
    active = await get_active_workout(message.from_user.id)
    if active:
        day_label = DAY_TYPES.get(active["day_type"], active["day_type"])
        await send_nav(
            message,
            f"⚠️ У тебя есть незавершённая тренировка!\n\n"
            f"📅 {active['date']} · <b>{day_label}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить", callback_data=f"resume:{active['id']}")],
                [InlineKeyboardButton(text="🗑 Начать заново", callback_data="discard_workout")],
            ])
        )
        return

    await state.clear()
    day_type, week_type, _ = await get_current_day(user)
    week_num = user["current_week"]
    day_label = DAY_TYPES.get(day_type, day_type.replace("_", " ").title())
    week_label = WEEK_TYPES.get(week_type, week_type.capitalize())

    await send_nav(
        message,
        f"💪 <b>Тренировки</b>\n\n"
        f"📅 Неделя {week_num} · {week_label}\n"
        f"Следующий день: <b>{day_label}</b>",
        reply_markup=workout_menu(day_label, week_label)
    )


@router.message(F.text == "📋 План тренировки")
async def show_plan(message: Message):
    user = await get_user(message.from_user.id)
    day_type, week_type, exercises = await get_current_day(user)
    day_label = DAY_TYPES.get(day_type, day_type.replace("_", " ").title())
    week_label = WEEK_TYPES.get(week_type, week_type.capitalize())

    if not exercises:
        await send_nav(message, "Программа не найдена. Пройди настройку /start", reply_markup=workout_menu(day_label, week_label))
        return

    text = f"📋 <b>{day_label} · {week_label}</b>\n\n{format_plan(exercises, week_type)}"
    await send_nav(message, text, reply_markup=workout_menu(day_label, week_label))


@router.message(WorkoutLogging.logging_sets, F.text.startswith("▶️ Начать:"))
async def guard_restart_during_workout(message: Message):
    """Защита от случайного перезапуска тренировки через кнопку меню."""
    await message.answer(
        "⚠️ Ты уже в тренировке! Введи результат подхода или нажми 🏁 Завершить."
    )


@router.message(F.text.startswith("▶️ Начать:"))
async def start_workout(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    day_type, week_type, exercises = await get_current_day(user)
    week_num = user["current_week"]
    day_label = DAY_TYPES.get(day_type, day_type.replace("_", " ").title())
    week_label = WEEK_TYPES.get(week_type, week_type.capitalize())

    if not exercises:
        await message.answer("Программа не найдена. Пройди настройку /start")
        return

    await discard_all_active_workouts(message.from_user.id)
    workout_id = await create_workout(message.from_user.id, today(), day_type, week_num, week_type)

    ex = exercises[0]
    cur_w, cur_r, cur_rpe = _init_set_defaults(ex)

    cur_rest = _parse_rest_seconds(ex["rest"]) if ex["sets"] > 1 else 0
    await state.set_state(WorkoutLogging.logging_sets)
    await state.update_data(
        workout_id=workout_id,
        day_type=day_type,
        week_type=week_type,
        exercises=exercises,
        ex_index=0,
        set_index=0,
        all_sets=[],
        current_weight=cur_w,
        current_reps=cur_r,
        current_rpe=cur_rpe,
        current_rest=cur_rest,
    )

    table = format_exercise_table(ex, [], 0)
    text = (
        f"🏋️ <b>{day_label} · {week_label} начата!</b>\n\n"
        f"<b>1. {ex['exercise']}</b>  ·  RPE {ex['rpe_range']}  ·  отдых {ex['rest']}\n\n"
        + table
        + f"\n\n<b>Подход 1/{ex['sets']}</b>"
    )
    sent = await message.answer(
        text, parse_mode="HTML",
        reply_markup=set_input_keyboard(cur_w, cur_r, cur_rpe, ex["weight"], cur_rest, ex["weight"] > 0),
    )
    await state.update_data(prompt_msg_id=sent.message_id)


def parse_set_input(text: str):
    """Парсит '50x8 8', '50 8 7 с лямками' → (weight, reps, rpe, notes)"""
    cleaned = text.lower().replace("rpe", " ").replace("×", "x").replace(",", ".")
    nums = re.findall(r'\d+\.?\d*', cleaned)
    if len(nums) < 2:
        return None
    weight = float(nums[0])
    reps = int(float(nums[1]))
    rpe = float(nums[2]) if len(nums) >= 3 else None
    # Заметка: всё что идёт после последнего числа
    last_idx = 2 if len(nums) >= 3 else 1
    last_end = 0
    for i, m in enumerate(re.finditer(r'\d+\.?\d*', cleaned)):
        if i == last_idx:
            last_end = m.end()
            break
    notes = re.sub(r'^[x\s.,;:]+', '', cleaned[last_end:]).strip() or None
    return weight, reps, rpe, notes


async def _advance_after_set(
    message: "Message", state: "FSMContext",
    weight: float, reps: int, rpe: float, notes: "str | None",
):
    """Сохраняет подход и показывает следующий промпт (отдых или новое упражнение)."""
    data = await state.get_data()
    exercises = data["exercises"]
    ex_index = data["ex_index"]
    set_index = data["set_index"]
    all_sets = data["all_sets"]
    workout_id = data["workout_id"]
    ex = exercises[ex_index]

    set_id = await save_set(workout_id, ex["exercise"], set_index + 1, ex["weight"], weight, reps, rpe, notes)
    all_sets.append({"exercise": ex["exercise"], "actual_weight": weight, "reps": reps, "rpe": rpe})

    next_set = set_index + 1
    next_ex = ex_index
    if next_set >= ex["sets"]:
        next_ex += 1
        next_set = 0

    await state.update_data(ex_index=next_ex, set_index=next_set, all_sets=all_sets,
                             last_set_id=set_id, last_set_ex_idx=ex_index, last_set_set_idx=set_index)
    await update_workout_progress(workout_id, next_ex, next_set)

    # Удаляем старые служебные сообщения
    if data.get("prompt_msg_id"):
        await _try_delete(message.bot, message.chat.id, data["prompt_msg_id"])
    if data.get("rest_info_msg_id"):
        await _try_delete(message.bot, message.chat.id, data["rest_info_msg_id"])

    if next_ex >= len(exercises):
        await finish_workout_flow(message, state)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    undo_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Отменить подход", callback_data=f"undo_set:{set_id}")
    ]])

    next_ex_obj = exercises[next_ex]
    is_new_ex = next_set == 0
    note_str = f"\n📝 <i>{notes}</i>" if notes else ""

    if is_new_ex:
        nw, nr, nrpe = _init_set_defaults(next_ex_obj)
        # Отдых берём от завершённого упражнения (пользователь мог скорректировать)
        rest_secs = data.get("current_rest") or _parse_rest_seconds(ex["rest"])
        # Для следующего упражнения сбрасываем current_rest по его плану
        next_rest = _parse_rest_seconds(next_ex_obj["rest"])
        await state.update_data(current_weight=nw, current_reps=nr, current_rpe=nrpe,
                                 current_rest=next_rest, rest_info_msg_id=None)
        text = f"✅ <b>{ex['exercise']}</b> — готово!{note_str}"
        sent = await message.answer(text, parse_mode="HTML", reply_markup=undo_kb)
        task = asyncio.create_task(
            _rest_timer_task(message.bot, message.chat.id, rest_secs)
        )
        _rest_timers[message.chat.id] = task
    else:
        nw = weight
        nr = _parse_reps_default(next_ex_obj["reps_range"])
        nrpe = _parse_rpe_default(next_ex_obj["rpe_range"])
        rest_secs = data.get("current_rest") or _parse_rest_seconds(ex["rest"])
        await state.update_data(current_weight=nw, current_reps=nr, current_rpe=nrpe,
                                 current_rest=rest_secs, rest_info_msg_id=None)
        table = format_exercise_table(ex, all_sets, next_set)
        text = (
            f"✅ {_fmt_weight(weight)}кг × {reps} повт. RPE {rpe}{note_str}\n\n"
            + table
            + f"\n\n<b>{ex['exercise']} — подход {next_set + 1}/{ex['sets']}</b>"
        )
        sent = await message.answer(text, parse_mode="HTML", reply_markup=undo_kb)
        task = asyncio.create_task(
            _rest_timer_task(message.bot, message.chat.id, rest_secs)
        )
        _rest_timers[message.chat.id] = task

    await state.update_data(prompt_msg_id=sent.message_id)


_NAV_PASSTHROUGH = frozenset({
    "🍽 Питание", "📊 Статистика", "⚙️ Настройки",
    "➕ Записать приём пищи", "➕ Записать еду",
    "💡 Совет по питанию",
    "📋 План тренировки", "📈 Прогресс",
    "🍴 Что съел сегодня", "📋 Сводка на сегодня", "📌 Шаблоны",
    "✏️ Изменить запись питания", "✏️ Изменить тренировку",
})


@router.message(WorkoutLogging.logging_sets, F.text.in_({"🏠 Главное меню", "💪 Тренировка"}))
async def abort_workout_on_nav(message: Message, state: FSMContext):
    _cancel_rest_timer(message.chat.id)
    await state.clear()
    await message.answer("Тренировка прервана.", reply_markup=main_menu())


@router.callback_query(WorkoutLogging.logging_sets, F.data == "workout_to_main")
async def abort_workout_to_main(callback: CallbackQuery, state: FSMContext):
    _cancel_rest_timer(callback.message.chat.id)
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Тренировка прервана.", reply_markup=main_menu())
    await callback.answer()


def parse_weight_command(text: str) -> tuple[str, float] | None:
    """Распознаёт команды изменения веса.
    Возвращает ('delta', value) или ('abs', value) или None.
    """
    t = text.strip().replace(",", ".")
    m = re.match(r'^([+-])(\d+(?:\.\d+)?)$', t)
    if m:
        sign, val = m.group(1), float(m.group(2))
        return ("delta", val if sign == "+" else -val)
    m = re.match(r'^(?:вес|weight)\s+(\d+(?:\.\d+)?)$', t.lower())
    if m:
        return ("abs", float(m.group(1)))
    return None


@router.message(WorkoutLogging.logging_sets, ~F.text.in_(_NAV_PASSTHROUGH), ~F.text.startswith("/"))
async def log_set(message: Message, state: FSMContext):
    if not message.text:
        return

    # Сначала проверяем команду изменения веса
    weight_cmd = parse_weight_command(message.text)
    if weight_cmd:
        _cancel_rest_timer(message.chat.id)
        await _try_delete(message.bot, message.chat.id, message.message_id)
        data = await state.get_data()
        cur_w = data.get("current_weight", 0)
        kind, val = weight_cmd
        new_w = (cur_w + val) if kind == "delta" else val
        if new_w <= 0:
            await message.answer("❌ Вес должен быть больше 0", parse_mode="HTML")
            return
        await state.update_data(current_weight=new_w)
        data = await state.get_data()  # обновлённые данные
        text, kb = _build_set_prompt(data)
        sent = await message.answer(f"✅ Вес → <b>{new_w:.1f} кг</b>\n\n" + text, parse_mode="HTML", reply_markup=kb)
        await track_msg(state, sent.message_id)
        return

    _cancel_rest_timer(message.chat.id)
    await _try_delete(message.bot, message.chat.id, message.message_id)

    data = await state.get_data()
    ex = data["exercises"][data["ex_index"]]
    parsed = parse_set_input(message.text)
    if not parsed:
        await message.answer(
            "❌ Не понял формат. Напиши: <code>50 8 7</code>\n"
            "💡 Изменить вес: <code>+2.5</code> / <code>-5</code> / <code>вес 80</code>",
            parse_mode="HTML"
        )
        return

    weight, reps, rpe, notes = parsed
    if rpe is None:
        rpe = 8.0
    await _advance_after_set(message, state, weight, reps, rpe, notes)


@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data.in_({"sw:+", "sw:-"}))
async def adjust_weight(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cur_w = max(0.0, data.get("current_weight", 0.0) + (2.5 if callback.data == "sw:+" else -2.5))
    await state.update_data(current_weight=cur_w)
    data["current_weight"] = cur_w
    text, kb = _build_set_prompt(data)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data.in_({"sr:+", "sr:-"}))
async def adjust_reps(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cur_r = max(1, data.get("current_reps", 8) + (1 if callback.data == "sr:+" else -1))
    await state.update_data(current_reps=cur_r)
    data["current_reps"] = cur_r
    text, kb = _build_set_prompt(data)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data.startswith("rpe:"))
async def select_rpe(callback: CallbackQuery, state: FSMContext):
    rpe = float(callback.data.split(":")[1])
    await state.update_data(current_rpe=rpe)
    data = await state.get_data()
    text, kb = _build_set_prompt(data)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data == "confirm_set")
async def confirm_set(callback: CallbackQuery, state: FSMContext):
    _cancel_rest_timer(callback.message.chat.id)
    data = await state.get_data()
    weight = data.get("current_weight", 0.0)
    reps = data.get("current_reps", 8)
    rpe = data.get("current_rpe", 8.0)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _advance_after_set(callback.message, state, weight, reps, rpe, None)


@router.callback_query(WorkoutLogging.logging_sets, F.data == "next_set")
async def next_set_cb(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    data = await state.get_data()
    text, kb = _build_set_prompt(data)
    sent = await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.update_data(prompt_msg_id=sent.message_id)
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data.in_({"rest_adj:+", "rest_adj:-"}))
async def adjust_rest(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cur = max(30, data.get("current_rest", 90) + (30 if callback.data == "rest_adj:+" else -30))
    await state.update_data(current_rest=cur)
    data["current_rest"] = cur
    text, kb = _build_set_prompt(data)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data.startswith("rest:"))
async def handle_rest_timer(callback: CallbackQuery, state: FSMContext):
    seconds = int(callback.data.split(":")[1])

    if seconds == 0:
        await callback.message.edit_reply_markup(reply_markup=None)
        data = await state.get_data()
        text, kb = _build_set_prompt(data)
        sent = await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
        await state.update_data(prompt_msg_id=sent.message_id)
        await callback.answer("Таймер пропущен")
        return

    mins, secs = divmod(seconds, 60)
    label = f"{mins}:{secs:02d}" if secs else f"{mins} мин"

    task = asyncio.create_task(
        _rest_timer_task(callback.bot, callback.message.chat.id, seconds)
    )
    _rest_timers[callback.message.chat.id] = task

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(f"⏱ Таймер {label} запущен")
    rest_info = await callback.message.answer(f"⏱ Отдыхаешь {label}... за 10 сек до конца напомню 🔔")
    await state.update_data(rest_info_msg_id=rest_info.message_id)


@router.callback_query(WorkoutLogging.logging_sets, F.data == "rest_ready")
async def rest_ready(callback: CallbackQuery, state: FSMContext):
    _cancel_rest_timer(callback.message.chat.id)
    await callback.message.edit_text("✅ <b>Подход начат!</b>", parse_mode="HTML", reply_markup=None)
    data = await state.get_data()
    text, kb = _build_set_prompt(data)
    sent = await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.update_data(prompt_msg_id=sent.message_id)
    await callback.answer()


@router.callback_query(F.data == "rest_ready")
async def rest_ready_no_state(callback: CallbackQuery):
    await callback.answer("Таймер уже завершён")


@router.callback_query(F.data.startswith("resume:"))
async def resume_workout(callback: CallbackQuery, state: FSMContext):
    """Продолжить незавершённую тренировку."""
    workout_id = int(callback.data.split(":")[1])
    user = await get_user(callback.from_user.id)

    # Получаем данные тренировки из БД
    from database.db import get_active_workout, get_workout_sets
    active = await get_active_workout(callback.from_user.id)
    if not active or active["id"] != workout_id:
        await callback.answer("Тренировка не найдена")
        return

    day_type = active["day_type"]
    week_type = active["week_type"]
    exercises = await get_user_program(callback.from_user.id, week_type, day_type)

    # Восстанавливаем already logged sets
    logged_sets = await get_workout_sets(workout_id)
    all_sets = [{"exercise": s["exercise"], "actual_weight": s["actual_weight"],
                 "reps": s["reps"], "rpe": s["rpe"]} for s in logged_sets]

    ex_index = active.get("ex_index", 0)
    set_index = active.get("set_index", 0)

    await state.set_state(WorkoutLogging.logging_sets)
    await state.update_data(
        workout_id=workout_id,
        day_type=day_type,
        week_type=week_type,
        exercises=exercises,
        ex_index=ex_index,
        set_index=set_index,
        all_sets=all_sets,
    )

    ex = exercises[ex_index]
    day_label = DAY_TYPES.get(day_type, day_type)
    cur_w, cur_r, cur_rpe = _init_set_defaults(ex)

    cur_rest = _parse_rest_seconds(ex["rest"]) if ex["sets"] > 1 else 0
    await state.update_data(current_weight=cur_w, current_reps=cur_r, current_rpe=cur_rpe,
                             current_rest=cur_rest)

    table = format_exercise_table(ex, all_sets, set_index)
    text = (
        f"▶️ <b>Продолжаем {day_label}!</b>\n\n"
        f"<b>{ex_index + 1}. {ex['exercise']}</b>  ·  RPE {ex['rpe_range']}  ·  отдых {ex['rest']}\n\n"
        + table
        + f"\n\n<b>Подход {set_index + 1}/{ex['sets']}</b>"
    )
    show_warmup = set_index == 0 and ex["weight"] > 0
    is_last_set = set_index == ex["sets"] - 1
    rest_show = 0 if is_last_set else cur_rest
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=set_input_keyboard(cur_w, cur_r, cur_rpe, ex["weight"], rest_show, show_warmup),
    )
    await state.update_data(prompt_msg_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(F.data == "discard_workout")
async def discard_workout(callback: CallbackQuery, state: FSMContext):
    """Отменить все незавершённые тренировки и начать новую."""
    await discard_all_active_workouts(callback.from_user.id)

    await state.clear()
    user = await get_user(callback.from_user.id)
    day_type, week_type, _ = await get_current_day(user)
    day_label = DAY_TYPES.get(day_type, day_type.replace("_", " ").title())
    week_label = WEEK_TYPES.get(week_type, week_type.capitalize())

    await callback.message.edit_text("🗑 Предыдущая тренировка отменена.", reply_markup=None)
    await callback.message.answer(
        f"💪 <b>Тренировки</b>\n\n"
        f"📅 Неделя {user['current_week']} · {week_label}\n"
        f"Следующий день: <b>{day_label}</b>",
        parse_mode="HTML",
        reply_markup=workout_menu(day_label, week_label)
    )
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data == "technique")
async def handle_technique(callback: CallbackQuery, state: FSMContext):
    import html as html_module
    data = await state.get_data()
    ex = data["exercises"][data["ex_index"]]

    await callback.answer()
    msg = await callback.message.answer(f"⏳ Загружаю технику <b>{ex['exercise']}</b>...", parse_mode="HTML")
    try:
        technique, gif_url = await asyncio.gather(
            get_exercise_technique(ex["exercise"]),
            get_exercise_gif(ex["exercise"]),
            return_exceptions=True,
        )

        if isinstance(technique, Exception):
            raise technique

        await msg.delete()

        if isinstance(gif_url, str) and gif_url:
            try:
                if gif_url.lower().endswith(".gif"):
                    await callback.message.answer_animation(gif_url)
                else:
                    await callback.message.answer_photo(gif_url)
            except Exception:
                pass

        await callback.message.answer(
            f"📖 <b>{html_module.escape(ex['exercise'])}</b>\n\n{html_module.escape(technique)}",
            parse_mode="HTML",
        )
    except Exception as e:
        await msg.edit_text(f"❌ Не удалось загрузить технику: {e}")


@router.callback_query(WorkoutLogging.logging_sets, F.data == "show_warmup")
async def handle_warmup(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ex = data["exercises"][data["ex_index"]]
    week_type = data.get("week_type", "volume")
    await callback.answer()
    await callback.message.answer(
        format_warmup(ex["exercise"], ex["weight"], week_type),
        parse_mode="HTML",
    )


@router.callback_query(WorkoutLogging.logging_sets, F.data == "finish_workout")
async def ask_finish(callback: CallbackQuery):
    await callback.message.answer("Завершить тренировку досрочно?", reply_markup=finish_keyboard())
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data == "continue_workout")
async def continue_workout(callback: CallbackQuery):
    await callback.message.answer("Продолжай! 💪")
    await callback.answer()


@router.callback_query(WorkoutLogging.logging_sets, F.data == "confirm_finish")
async def force_finish(callback: CallbackQuery, state: FSMContext):
    await finish_workout_flow(callback.message, state)
    await callback.answer()


async def finish_workout_flow(message: Message, state: FSMContext):
    data = await state.get_data()
    workout_id = data["workout_id"]
    all_sets = data["all_sets"]
    day_type = data["day_type"]
    week_type = data["week_type"]
    user = await get_user(message.chat.id)

    # Считаем тоннаж и средний RPE
    tonnage = sum(s["actual_weight"] * s["reps"] for s in all_sets)
    avg_rpe = sum(s["rpe"] for s in all_sets) / len(all_sets) if all_sets else 0
    await finish_workout(workout_id, tonnage, avg_rpe)

    # Продвигаем программу
    day_index = user["current_day_index"]
    current_week_type = user["current_week_type"]
    day_types = await get_user_day_types(user["user_id"], current_week_type)
    week_types = await get_user_week_types(user["user_id"])

    next_day_index = day_index + 1
    next_week_type = current_week_type
    next_week_num = user["current_week"]

    if next_day_index >= len(day_types):
        next_day_index = 0
        # переходим к следующему типу недели
        if week_types:
            curr_idx = week_types.index(current_week_type) if current_week_type in week_types else 0
            next_week_type = week_types[(curr_idx + 1) % len(week_types)]
        next_week_num = user["current_week"] + 1

    await update_user(message.chat.id,
                      current_day_index=next_day_index,
                      current_week_type=next_week_type,
                      current_week=next_week_num)

    await state.clear()

    next_day_types = await get_user_day_types(user["user_id"], next_week_type)
    next_day_label = DAY_TYPES.get(next_day_types[next_day_index % len(next_day_types)], next_day_types[next_day_index % len(next_day_types)].replace("_", " ").title()) if next_day_types else "—"
    next_week_label = WEEK_TYPES.get(next_week_type, next_week_type.capitalize())

    finish_msg = await message.answer(
        f"🏁 <b>Тренировка завершена!</b>\n\n"
        f"📊 Тоннаж: <b>{tonnage:.0f} кг</b>\n"
        f"💥 Средний RPE: <b>{avg_rpe:.1f}</b>\n"
        f"Подходов записано: {len(all_sets)}\n\n"
        f"⏳ Генерирую анализ...",
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    track_msg(message.chat.id, finish_msg.message_id)

    # AI анализ
    try:
        prev = await get_last_workout_by_day(message.chat.id, day_type)
        prev_text = "Нет данных"
        if prev and prev["id"] != workout_id:
            prev_sets = await get_workout_sets(prev["id"])
            if prev_sets:
                prev_text = f"Дата: {prev['date']}, тоннаж: {prev['total_tonnage']:.0f}кг, RPE: {prev['avg_rpe']:.1f}\n"
                prev_text += "\n".join(f"{s['exercise']}: {s['actual_weight']}кг × {s['reps']} RPE{s['rpe']}" for s in prev_sets[:10])

        day_label = DAY_TYPES.get(day_type, day_type)
        week_label = WEEK_TYPES.get(week_type, week_type)
        analysis = await analyze_workout(
            day_label, week_label,
            all_sets, prev_text, user["weight"]
        )
        analysis_msg = await message.answer(f"🤖 <b>Анализ тренировки:</b>\n\n{analysis}", parse_mode="HTML")
        track_msg(message.chat.id, analysis_msg.message_id)
    except Exception as e:
        import logging, traceback
        logging.getLogger(__name__).error(f"Ошибка анализа: {traceback.format_exc()}")
        err_msg = await message.answer(f"⚠️ Анализ недоступен: {e}")
        track_msg(message.chat.id, err_msg.message_id)

    # Прогрессия весов (не применяем на разгрузочной неделе)
    if week_type != "deload":
        progression = _calculate_progression(all_sets, data["exercises"])
        if progression:
            changed = [p for p in progression if p["new_weight"] != p["old_weight"]]
            for p in changed:
                await update_exercise_weight(
                    message.chat.id, week_type, day_type,
                    p["exercise"], p["new_weight"]
                )
            lines_prog = []
            for p in progression:
                w_old = _fmt_weight(p["old_weight"])
                w_new = _fmt_weight(p["new_weight"])
                if p["new_weight"] != p["old_weight"]:
                    lines_prog.append(f"{p['icon']} <b>{p['exercise']}</b>: {w_old} → {w_new}кг (RPE {p['avg_rpe']:.1f})")
                else:
                    lines_prog.append(f"{p['icon']} <b>{p['exercise']}</b>: {w_old}кг (RPE {p['avg_rpe']:.1f})")
            prog_msg = await message.answer(
                "📈 <b>Прогрессия на следующую тренировку:</b>\n\n" + "\n".join(lines_prog),
                parse_mode="HTML"
            )
            track_msg(message.chat.id, prog_msg.message_id)

    next_msg = await message.answer(
        f"Следующая тренировка: <b>{next_day_label}</b> · {next_week_label}",
        parse_mode="HTML"
    )
    track_msg(message.chat.id, next_msg.message_id)


@router.message(F.text == "📈 Прогресс")
async def show_progress(message: Message):
    from database.db import get_last_workouts
    user = await get_user(message.from_user.id)
    workouts = await get_last_workouts(message.from_user.id, 6)
    day_type, week_type, _ = await get_current_day(user)
    day_label = DAY_TYPES.get(day_type, day_type.replace("_", " ").title())
    week_label = WEEK_TYPES.get(week_type, week_type.capitalize())
    if not workouts:
        await send_nav(message, "Нет данных о тренировках.", reply_markup=workout_menu(day_label, week_label))
        return

    lines = ["📈 <b>Последние тренировки:</b>\n"]
    for w in workouts:
        w_day_label = DAY_TYPES.get(w["day_type"], w["day_type"])
        w_week_label = WEEK_TYPES.get(w["week_type"], w["week_type"])
        lines.append(
            f"📅 {w['date']} · {w_day_label} ({w_week_label})\n"
            f"   🏋️ Тоннаж: {w['total_tonnage']:.0f}кг · RPE: {w['avg_rpe']:.1f}"
        )
    await send_nav(message, "\n".join(lines), reply_markup=workout_menu(day_label, week_label))


@router.callback_query(F.data.startswith("undo_set:"))
async def cb_undo_set(callback: CallbackQuery, state: FSMContext):
    set_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()

    if data.get("last_set_id") != set_id:
        await callback.answer("Отменить можно только последний подход", show_alert=True)
        return

    await delete_workout_set(set_id)

    ex_index = data["last_set_ex_idx"]
    set_index = data["last_set_set_idx"]
    all_sets = data.get("all_sets", [])
    if all_sets:
        all_sets.pop()

    await state.update_data(
        ex_index=ex_index, set_index=set_index,
        all_sets=all_sets, last_set_id=None,
        last_set_ex_idx=None, last_set_set_idx=None,
    )
    workout_id = data["workout_id"]
    await update_workout_progress(workout_id, ex_index, set_index)

    try:
        await callback.message.delete()
    except Exception:
        pass

    exercises = data["exercises"]
    ex = exercises[ex_index]
    cur_w = data.get("current_weight", ex["weight"])
    cur_r = data.get("current_reps", 5)
    cur_rpe = data.get("current_rpe", 8.0)
    cur_rest = data.get("current_rest") or _parse_rest_seconds(ex["rest"])
    text, kb = _build_set_prompt({**data, "ex_index": ex_index, "set_index": set_index,
                                   "current_weight": cur_w, "current_reps": cur_r,
                                   "current_rpe": cur_rpe, "current_rest": cur_rest})
    sent = await callback.message.answer(
        f"↩️ Подход отменён. Повтори ввод.\n\n{text}", parse_mode="HTML", reply_markup=kb
    )
    await state.update_data(prompt_msg_id=sent.message_id)
    await callback.answer("Подход удалён")


@router.callback_query(F.data == "go_workout")
async def cb_go_workout(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает кнопку из напоминания о тренировке."""
    await callback.answer()
    await callback.message.delete()
    await start_workout(callback.message, state)
