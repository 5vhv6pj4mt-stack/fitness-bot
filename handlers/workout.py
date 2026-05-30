import re
import asyncio
from datetime import date
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import (get_user, update_user, create_workout, save_set,
                          finish_workout, get_last_workout_by_day, get_workout_sets,
                          get_user_program, get_user_day_types, get_user_week_types,
                          update_workout_progress, get_active_workout, discard_all_active_workouts)
from keyboards.keyboards import main_menu, workout_menu, workout_logging_keyboard, finish_keyboard, rest_timer_keyboard
from services.ai_service import analyze_workout, get_exercise_technique, get_exercise_gif
from states.states import WorkoutLogging
from handlers.nav import send_nav

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
            await bot.send_message(chat_id, "⏰ <b>Время вышло! Следующий подход 💪</b>", parse_mode="HTML")
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
        await send_nav(message, "Программа не найдена. Пройди настройку /start")
        return

    text = f"📋 <b>{day_label} · {week_label}</b>\n\n{format_plan(exercises, week_type)}"
    await send_nav(message, text)


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

    await state.set_state(WorkoutLogging.logging_sets)
    await state.update_data(
        workout_id=workout_id,
        day_type=day_type,
        week_type=week_type,
        exercises=exercises,
        ex_index=0,
        set_index=0,
        all_sets=[],
    )

    ex = exercises[0]
    w = f"{ex['weight']}кг" if ex['weight'] > 0 else "свой вес"
    sent = await message.answer(
        f"🏋️ <b>{day_label} · {week_label} начата!</b>\n\n"
        f"<b>1. {ex['exercise']}</b>\n"
        f"Plan: {ex['sets']}×{ex['reps_range']} @ {w}, RPE {ex['rpe_range']}\n"
        f"Отдых: {ex['rest']}\n\n"
        f"<b>Подход 1/{ex['sets']}:</b>\n"
        f"Введи результат в формате: <code>вес × повторы RPE</code>\n"
        f"Пример: <code>50 × 8 RPE8</code> или <code>50x8 8</code>",
        parse_mode="HTML",
        reply_markup=workout_logging_keyboard(ex['exercise'], 1, ex['sets'], ex['weight'], ex['reps_range'])
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


_NAV_PASSTHROUGH = frozenset({
    "🍽 Питание", "📊 Статистика", "⚙️ Настройки",
    "➕ Записать приём пищи", "➕ Записать еду",
    "📋 Итог за сегодня", "💡 Совет по питанию",
    "📋 План тренировки", "📈 Прогресс",
})


@router.message(WorkoutLogging.logging_sets, F.text.in_({"🏠 Главное меню", "💪 Тренировка"}))
async def abort_workout_on_nav(message: Message, state: FSMContext):
    _cancel_rest_timer(message.chat.id)
    await state.clear()
    await message.answer("Тренировка прервана.", reply_markup=main_menu())


@router.message(WorkoutLogging.logging_sets, ~F.text.in_(_NAV_PASSTHROUGH), ~F.text.startswith("/"))
async def log_set(message: Message, state: FSMContext):
    if not message.text:
        return

    # Отменяем предыдущий таймер если пользователь ввёл подход раньше
    _cancel_rest_timer(message.chat.id)

    # Удаляем сообщение пользователя с вводом подхода
    await _try_delete(message.bot, message.chat.id, message.message_id)

    data = await state.get_data()
    exercises = data["exercises"]
    ex_index = data["ex_index"]
    set_index = data["set_index"]
    all_sets = data["all_sets"]
    workout_id = data["workout_id"]

    ex = exercises[ex_index]
    parsed = parse_set_input(message.text)

    if not parsed:
        await message.answer(
            "❌ Не понял формат. Напиши например: <code>50 8 7</code>",
            parse_mode="HTML"
        )
        return

    weight, reps, rpe, notes = parsed
    if rpe is None:
        rpe = 8.0

    await save_set(workout_id, ex["exercise"], set_index + 1, ex["weight"], weight, reps, rpe, notes)
    all_sets.append({"exercise": ex["exercise"], "actual_weight": weight, "reps": reps, "rpe": rpe})

    next_set = set_index + 1
    next_ex = ex_index

    if next_set >= ex["sets"]:
        next_ex += 1
        next_set = 0

    await state.update_data(ex_index=next_ex, set_index=next_set, all_sets=all_sets)
    # Сохраняем прогресс в БД — чтобы можно было продолжить после выхода
    await update_workout_progress(workout_id, next_ex, next_set)

    # Тренировка завершена
    if next_ex >= len(exercises):
        await finish_workout_flow(message, state)
        return

    next_exercise = exercises[next_ex]
    is_new_ex = next_set == 0
    w = f"{next_exercise['weight']}кг" if next_exercise['weight'] > 0 else "свой вес"

    note_str = f"\n📝 <i>{notes}</i>" if notes else ""

    if is_new_ex:
        set_info = (
            f"✅ <b>{ex['exercise']}</b> — готово!{note_str}\n\n"
            f"<b>{next_ex + 1}. {next_exercise['exercise']}</b>\n"
            f"План: {next_exercise['sets']}×{next_exercise['reps_range']} @ {w}, RPE {next_exercise['rpe_range']}\n\n"
            f"<b>Подход 1/{next_exercise['sets']}</b> — введи результат:"
        )
    else:
        set_info = (
            f"✅ {weight}кг × {reps} повт. RPE {rpe}{note_str}\n\n"
            f"<b>{ex['exercise']} — подход {next_set + 1}/{ex['sets']}</b> — введи результат:"
        )

    # Удаляем предыдущий промпт и инфо-сообщение об отдыхе
    if data.get("prompt_msg_id"):
        await _try_delete(message.bot, message.chat.id, data["prompt_msg_id"])
    if data.get("rest_info_msg_id"):
        await _try_delete(message.bot, message.chat.id, data["rest_info_msg_id"])

    if is_new_ex:
        # Новое упражнение — таймер не нужен, показываем skip/finish
        sent = await message.answer(
            set_info,
            parse_mode="HTML",
            reply_markup=workout_logging_keyboard(
                next_exercise['exercise'], 1, next_exercise['sets'],
                next_exercise['weight'], next_exercise['reps_range']
            )
        )
    else:
        # Следующий подход того же упражнения — показываем таймер отдыха
        sent = await message.answer(set_info, parse_mode="HTML", reply_markup=rest_timer_keyboard())

    await state.update_data(prompt_msg_id=sent.message_id, rest_info_msg_id=None)


@router.callback_query(WorkoutLogging.logging_sets, F.data.startswith("rest:"))
async def handle_rest_timer(callback: CallbackQuery, state: FSMContext):
    seconds = int(callback.data.split(":")[1])

    if seconds == 0:
        await callback.message.edit_reply_markup(reply_markup=None)
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
async def rest_ready(callback: CallbackQuery):
    """Пользователь нажал 'Готов' до истечения таймера."""
    _cancel_rest_timer(callback.message.chat.id)
    await callback.message.edit_text("✅ <b>Подход начат!</b>", parse_mode="HTML", reply_markup=None)
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
    w = f"{ex['weight']}кг" if ex['weight'] > 0 else "свой вес"
    day_label = DAY_TYPES.get(day_type, day_type)

    await callback.message.edit_text(
        f"▶️ <b>Продолжаем {day_label}!</b>\n\n"
        f"Подходов уже записано: {len(all_sets)}\n\n"
        f"<b>{ex_index + 1}. {ex['exercise']}</b>\n"
        f"План: {ex['sets']}×{ex['reps_range']} @ {w}\n\n"
        f"<b>Подход {set_index + 1}/{ex['sets']}</b> — введи результат:",
        parse_mode="HTML",
        reply_markup=workout_logging_keyboard(ex["exercise"], set_index + 1, ex["sets"], ex["weight"], ex["reps_range"])
    )
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


@router.callback_query(WorkoutLogging.logging_sets, F.data.startswith("skip_set:"))
async def skip_set(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    exercises = data["exercises"]
    ex_index = data["ex_index"]
    set_index = data["set_index"]

    ex = exercises[ex_index]
    next_set = set_index + 1
    next_ex = ex_index

    if next_set >= ex["sets"]:
        next_ex += 1
        next_set = 0

    await state.update_data(ex_index=next_ex, set_index=next_set)

    if next_ex >= len(exercises):
        await finish_workout_flow(callback.message, state)
        await callback.answer()
        return

    next_exercise = exercises[next_ex]
    w = f"{next_exercise['weight']}кг" if next_exercise['weight'] > 0 else "свой вес"
    await callback.message.answer(
        f"⏭ Подход пропущен.\n\n"
        f"<b>{next_ex + 1}. {next_exercise['exercise']}</b>\n"
        f"Plan: {next_exercise['sets']}×{next_exercise['reps_range']} @ {w}\n\n"
        f"<b>Подход {next_set + 1}/{next_exercise['sets']}:</b>",
        parse_mode="HTML"
    )
    await callback.answer()


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

    await message.answer(
        f"🏁 <b>Тренировка завершена!</b>\n\n"
        f"📊 Тоннаж: <b>{tonnage:.0f} кг</b>\n"
        f"💥 Средний RPE: <b>{avg_rpe:.1f}</b>\n"
        f"Подходов записано: {len(all_sets)}\n\n"
        f"⏳ Генерирую анализ...",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

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
        await message.answer(f"🤖 <b>Анализ тренировки:</b>\n\n{analysis}", parse_mode="HTML")
    except Exception as e:
        import logging, traceback
        logging.getLogger(__name__).error(f"Ошибка анализа: {traceback.format_exc()}")
        await message.answer(f"⚠️ Анализ недоступен: {e}")

    await message.answer(
        f"Следующая тренировка: <b>{next_day_label}</b> · {next_week_label}",
        parse_mode="HTML"
    )


@router.message(F.text == "📈 Прогресс")
async def show_progress(message: Message):
    from database.db import get_last_workouts
    workouts = await get_last_workouts(message.from_user.id, 6)
    if not workouts:
        await send_nav(message, "Нет данных о тренировках.")
        return

    lines = ["📈 <b>Последние тренировки:</b>\n"]
    for w in workouts:
        day_label = DAY_TYPES.get(w["day_type"], w["day_type"])
        week_label = WEEK_TYPES.get(w["week_type"], w["week_type"])
        lines.append(
            f"📅 {w['date']} · {day_label} ({week_label})\n"
            f"   🏋️ Тоннаж: {w['total_tonnage']:.0f}кг · RPE: {w['avg_rpe']:.1f}"
        )
    await send_nav(message, "\n".join(lines))
