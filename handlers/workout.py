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
                          update_exercise_weight)
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


def parse_weight_command(text: str) -> float | None:
    """Распознаёт команды изменения веса.

    Форматы:
    - '+2.5' или '-5' — относительное изменение (возвращает delta как float со знаком)
    - 'вес 100' или 'Вес 87.5' — абсолютная установка (возвращает значение как положительный float)

    Возвращает float — delta (может быть отрицательной) или абсолютное значение,
    либо None если текст не распознан как команда изменения