from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import get_user, update_user, get_meal_reminders, set_meal_reminder, save_user_program, delete_user_program
from keyboards.keyboards import main_menu
from states.states import Setup, ReminderSettings
from handlers.nav import send_nav, track_msg
from services.scheduler import setup_daily_reminders, setup_morning_brief, remove_morning_brief

router = Router()


_PROGRESS_NOTIFS = [
    ("notify_pr",             "🏆 Личные рекорды"),
    ("notify_streak",         "🔥 Стрики тренировок"),
    ("notify_plateau",        "⚠️ Детекция плато"),
    ("notify_overtraining",   "🚨 Перетренированность"),
    ("notify_weekly_report",  "📋 Еженедельный отчёт"),
]

_BRIEF_SECTIONS = [
    ("brief_workout",   "💪 План тренировки",        1),
    ("brief_yesterday", "📊 Итоги вчера",            1),
    ("brief_nutrient",  "🥩 Нутриент-акцент",        1),
    ("brief_recovery",  "😴 Статус восстановления",  1),
    ("brief_week_prog", "📈 Прогресс недели",         1),
    ("brief_water",     "💧 Норма воды",             1),
    ("brief_tip",       "💡 Совет дня",              1),
    ("brief_food_idea", "🍳 Идея завтрака (AI)",      0),
]


def _progress_notif_kb(user: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label in _PROGRESS_NOTIFS:
        enabled = user.get(key, 1)
        icon = "✅" if enabled else "❌"
        rows.append([InlineKeyboardButton(text=f"{icon} {label}", callback_data=f"pnotif_toggle:{key}")])
    # Кнопка для утреннего брифа — ведёт в подменю
    brief_on = user.get("notify_morning_brief", 1)
    brief_icon = "✅" if brief_on else "❌"
    rows.append([InlineKeyboardButton(
        text=f"{brief_icon} 🌅 Утренний бриф (8:00) →",
        callback_data="brief_settings"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _brief_settings_kb(user: dict) -> InlineKeyboardMarkup:
    rows = []
    # Мастер-тогл
    master = user.get("notify_morning_brief", 1)
    master_icon = "✅" if master else "❌"
    rows.append([InlineKeyboardButton(
        text=f"{master_icon} Бриф включён",
        callback_data="pnotif_toggle:notify_morning_brief"
    )])
    rows.append([InlineKeyboardButton(text="─────────────────", callback_data="noop")])
    # Секции
    for key, label, default in _BRIEF_SECTIONS:
        enabled = user.get(key, default)
        icon = "✅" if enabled else "❌"
        rows.append([InlineKeyboardButton(text=f"{icon} {label}", callback_data=f"brief_toggle:{key}")])
    rows.append([InlineKeyboardButton(text="← Назад", callback_data="back_to_notifs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _reminders_kb(reminders: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for r in reminders:
        icon = "✅" if r["enabled"] else "❌"
        time = f"{r['hour']:02d}:{r['minute']:02d}"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {r['name']} — {time}",
            callback_data=f"rem_detail:{r['meal_id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _meal_detail_kb(meal_id: str, enabled: int) -> InlineKeyboardMarkup:
    toggle_text = "🔕 Выключить" if enabled else "🔔 Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"rem_toggle:{meal_id}"),
            InlineKeyboardButton(text="🕐 Изменить время", callback_data=f"rem_time:{meal_id}"),
        ],
        [InlineKeyboardButton(text="← Назад", callback_data="rem_list")],
    ])


@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    user = await get_user(message.from_user.id)
    goal_labels = {"mass": "Набор массы", "loss": "Похудение", "strength": "Сила", "tone": "Тонус"}
    utc_offset = user.get("utc_offset", 0)
    tz_str = f"UTC+{utc_offset}" if utc_offset >= 0 else f"UTC{utc_offset}"
    await send_nav(
        message,
        f"⚙️ <b>Твои настройки</b>\n\n"
        f"👤 Имя: {user.get('name', '—')}\n"
        f"⚖️ Вес: {user.get('weight', '—')} кг\n"
        f"📏 Рост: {user.get('height', '—')} см\n"
        f"🎂 Возраст: {user.get('age', '—')} лет\n"
        f"🎯 Цель: {goal_labels.get(user.get('goal', ''), '—')}\n"
        f"📅 Дней в неделю: {user.get('days_per_week', '—')}\n"
        f"🕐 Часовой пояс: {tz_str}\n\n"
        f"<b>Цели по питанию:</b>\n"
        f"🔥 {user.get('goal_calories', 0)} ккал\n"
        f"🥩 Белок: {user.get('goal_protein', 0)}г\n"
        f"🌾 Углеводы: {user.get('goal_carbs', 0)}г\n"
        f"🫒 Жиры: {user.get('goal_fat', 0)}г\n\n"
        f"Чтобы обновить вес — напиши: <code>вес 75</code>\n"
        f"Чтобы сменить часовой пояс — напиши: <code>tz +7</code>\n"
        f"Чтобы переделать программу — напиши /start",
        reply_markup=main_menu(),
    )
    reminders = await get_meal_reminders(message.from_user.id)
    sent = await message.answer(
        "🔔 <b>Напоминания о питании</b>",
        reply_markup=_reminders_kb(reminders),
        parse_mode="HTML",
    )
    track_msg(message.from_user.id, sent.message_id)

    sent2 = await message.answer(
        "📊 <b>Уведомления о прогрессе</b>",
        reply_markup=_progress_notif_kb(user),
        parse_mode="HTML",
    )
    track_msg(message.from_user.id, sent2.message_id)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "brief_settings")
async def cb_brief_settings(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    await callback.message.edit_text(
        "🌅 <b>Настройки утреннего брифа</b>\n\n"
        "Включай или выключай разделы брифа.\n"
        "Отправляется в 8:00 каждый день.",
        reply_markup=_brief_settings_kb(user),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_notifs")
async def cb_back_to_notifs(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    await callback.message.edit_text(
        "📊 <b>Уведомления о прогрессе</b>",
        reply_markup=_progress_notif_kb(user),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("brief_toggle:"))
async def cb_brief_toggle(callback: CallbackQuery):
    key = callback.data.split(":", 1)[1]
    valid_keys = {k for k, _, _ in _BRIEF_SECTIONS}
    if key not in valid_keys:
        await callback.answer()
        return
    user = await get_user(callback.from_user.id)
    default = next((d for k, _, d in _BRIEF_SECTIONS if k == key), 1)
    new_val = 0 if user.get(key, default) else 1
    await update_user(callback.from_user.id, **{key: new_val})
    user[key] = new_val
    await callback.message.edit_reply_markup(reply_markup=_brief_settings_kb(user))
    await callback.answer("Включено ✅" if new_val else "Выключено ❌")


@router.callback_query(F.data.startswith("pnotif_toggle:"))
async def cb_pnotif_toggle(callback: CallbackQuery):
    key = callback.data.split(":", 1)[1]
    valid_keys = {k for k, _ in _PROGRESS_NOTIFS} | {"notify_morning_brief"}
    if key not in valid_keys:
        await callback.answer()
        return
    user = await get_user(callback.from_user.id)
    new_val = 0 if user.get(key, 1) else 1
    await update_user(callback.from_user.id, **{key: new_val})
    user[key] = new_val
    if key == "notify_morning_brief":
        if new_val:
            setup_morning_brief(callback.from_user.id,
                                user.get("morning_brief_hour", 8),
                                user.get("morning_brief_minute", 0))
        else:
            remove_morning_brief(callback.from_user.id)
        # обновляем подменю брифа (если вызвано оттуда)
        try:
            await callback.message.edit_reply_markup(reply_markup=_brief_settings_kb(user))
        except Exception:
            pass
        await callback.answer("Включено ✅" if new_val else "Выключено ❌")
        return
    await callback.message.edit_reply_markup(reply_markup=_progress_notif_kb(user))
    await callback.answer("Включено ✅" if new_val else "Выключено ❌")


@router.callback_query(F.data == "rem_list")
async def cb_rem_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    reminders = await get_meal_reminders(callback.from_user.id)
    await callback.message.edit_text(
        "🔔 <b>Напоминания о питании</b>",
        reply_markup=_reminders_kb(reminders),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rem_detail:"))
async def cb_rem_detail(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    meal_id = callback.data.split(":", 1)[1]
    reminders = await get_meal_reminders(callback.from_user.id)
    meal = next((r for r in reminders if r["meal_id"] == meal_id), None)
    if not meal:
        await callback.answer()
        return
    status = "включено" if meal["enabled"] else "выключено"
    time = f"{meal['hour']:02d}:{meal['minute']:02d}"
    await callback.message.edit_text(
        f"🔔 <b>{meal['name']}</b> — {time} ({status})",
        reply_markup=_meal_detail_kb(meal_id, meal["enabled"]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rem_toggle:"))
async def cb_rem_toggle(callback: CallbackQuery):
    meal_id = callback.data.split(":", 1)[1]
    reminders = await get_meal_reminders(callback.from_user.id)
    meal = next((r for r in reminders if r["meal_id"] == meal_id), None)
    if not meal:
        await callback.answer()
        return
    new_enabled = 0 if meal["enabled"] else 1
    await set_meal_reminder(callback.from_user.id, meal_id, new_enabled, meal["hour"], meal["minute"])
    updated = await get_meal_reminders(callback.from_user.id)
    setup_daily_reminders(callback.from_user.id, updated)
    status = "включено" if new_enabled else "выключено"
    time = f"{meal['hour']:02d}:{meal['minute']:02d}"
    await callback.message.edit_text(
        f"🔔 <b>{meal['name']}</b> — {time} ({status})",
        reply_markup=_meal_detail_kb(meal_id, new_enabled),
        parse_mode="HTML",
    )
    await callback.answer("✅ Сохранено")


@router.callback_query(F.data.startswith("rem_time:"))
async def cb_rem_time(callback: CallbackQuery, state: FSMContext):
    meal_id = callback.data.split(":", 1)[1]
    await state.set_state(ReminderSettings.waiting_time)
    await state.update_data(meal_id=meal_id, reminder_msg_id=callback.message.message_id)
    await callback.message.edit_text(
        "🕐 Введи новое время в формате <code>ЧЧ:ММ</code>\n"
        "Например: <code>09:00</code> или <code>20:30</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"rem_detail:{meal_id}")
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ReminderSettings.waiting_time)
async def rem_time_input(message: Message, state: FSMContext):
    data = await state.get_data()
    meal_id = data.get("meal_id")
    msg_id = data.get("reminder_msg_id")

    try:
        parts = message.text.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError, AttributeError):
        await message.answer(
            "❌ Неверный формат. Введи время как <code>09:00</code>",
            parse_mode="HTML",
        )
        return

    reminders = await get_meal_reminders(message.from_user.id)
    meal = next((r for r in reminders if r["meal_id"] == meal_id), None)
    if not meal:
        await state.clear()
        return

    await set_meal_reminder(message.from_user.id, meal_id, meal["enabled"], hour, minute)
    updated = await get_meal_reminders(message.from_user.id)
    setup_daily_reminders(message.from_user.id, updated)
    await state.clear()

    try:
        await message.delete()
    except Exception:
        pass

    time_str = f"{hour:02d}:{minute:02d}"
    status = "включено" if meal["enabled"] else "выключено"
    if msg_id:
        try:
            await message.bot.edit_message_text(
                f"🔔 <b>{meal['name']}</b> — {time_str} ({status})",
                chat_id=message.chat.id,
                message_id=msg_id,
                reply_markup=_meal_detail_kb(meal_id, meal["enabled"]),
                parse_mode="HTML",
            )
        except Exception:
            pass
    await message.answer(
        f"✅ Напоминание <b>{meal['name']}</b> теперь в {time_str}",
        parse_mode="HTML",
    )


@router.message(F.text.lower().startswith("вес "))
async def update_weight(message: Message):
    try:
        weight = float(message.text.split()[1].replace(",", "."))
        await update_user(message.from_user.id, weight=weight)
        await message.answer(f"✅ Вес обновлён: {weight} кг")
    except (ValueError, IndexError):
        await message.answer("Формат: <code>вес 75.5</code>", parse_mode="HTML")


@router.message(Command("reset"))
async def reset_command(message: Message):
    await message.answer(
        "⚠️ <b>Сброс программы тренировок</b>\n\n"
        "Это обнулит счётчик недели и перегенерирует программу по твоему профилю.\n"
        "Данные о тренировках и питании <b>не удаляются</b>.\n\n"
        "Продолжить?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да, сбросить", callback_data="reset_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="reset_cancel"),
        ]]),
    )


@router.callback_query(F.data == "reset_cancel")
async def cb_reset_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.callback_query(F.data == "reset_confirm")
async def cb_reset_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text("⏳ Сбрасываю программу...")
    await callback.answer()

    PRESET_USER_ID = 311739548

    try:
        if user_id == PRESET_USER_ID:
            from database.program_data import PROGRAM
            program_flat = []
            for week_type, days in PROGRAM.items():
                for day_type, exercises in days.items():
                    for i, ex in enumerate(exercises):
                        program_flat.append({
                            "week_type": week_type, "day_type": day_type, "order_num": i,
                            "exercise": ex["exercise"], "sets": ex["sets"],
                            "reps_range": ex["reps"], "weight": ex["weight"],
                            "rpe_range": ex["rpe"], "rest": ex["rest"],
                        })
            await save_user_program(user_id, program_flat)
            await update_user(user_id, current_week=1, current_week_type="strength", current_day_index=0)
            await callback.message.edit_text(
                "✅ <b>Программа сброшена!</b>\n\nНеделя 1 · Силовая · День 1\nЖми <b>Тренировка</b> чтобы начать!",
                parse_mode="HTML",
            )
        else:
            user = await get_user(user_id)
            await callback.message.edit_text("⏳ Генерирую программу через AI... (10–20 сек)")
            from services.ai_service import generate_program
            program, nutrition = await generate_program(user)
            await save_user_program(user_id, program)
            week_types = list(dict.fromkeys(ex["week_type"] for ex in program))
            await update_user(
                user_id,
                goal_calories=nutrition["calories"], goal_protein=nutrition["protein"],
                goal_carbs=nutrition["carbs"], goal_fat=nutrition["fat"],
                current_week=1, current_week_type=week_types[0], current_day_index=0,
            )
            await callback.message.edit_text(
                f"✅ <b>Программа перегенерирована!</b>\n\n"
                f"🔥 {nutrition['calories']} ккал · 🥩 {nutrition['protein']}г белка\n\n"
                f"Жми <b>Тренировка</b> чтобы начать!",
                parse_mode="HTML",
            )
    except Exception as e:
        await callback.message.edit_text(f"⚠️ Ошибка: {e}\n\nПопробуй ещё раз через /reset")


@router.message(F.text.lower().regexp(r"^tz\s*[+-]\d+$"))
async def update_timezone(message: Message):
    try:
        offset = int(message.text.strip().split()[1])
        if not -12 <= offset <= 14:
            raise ValueError
        await update_user(message.from_user.id, utc_offset=offset)
        tz_str = f"UTC+{offset}" if offset >= 0 else f"UTC{offset}"
        await message.answer(f"✅ Часовой пояс обновлён: {tz_str}", parse_mode="HTML")
    except (ValueError, IndexError):
        await message.answer("Формат: <code>tz +7</code> или <code>tz -5</code>", parse_mode="HTML")


@router.message(Command("brief"))
async def cmd_brief(message: Message):
    """Тестовая команда — отправляет утренний бриф прямо сейчас."""
    from services.scheduler import _send_morning_brief
    await message.answer("⏳ Генерирую бриф...")
    await _send_morning_brief(message.from_user.id)
