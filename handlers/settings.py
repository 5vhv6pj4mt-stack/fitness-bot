from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import get_user, update_user, get_meal_reminders, set_meal_reminder
from keyboards.keyboards import main_menu
from states.states import Setup, ReminderSettings
from handlers.nav import send_nav, track_msg
from services.scheduler import setup_daily_reminders

router = Router()


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
