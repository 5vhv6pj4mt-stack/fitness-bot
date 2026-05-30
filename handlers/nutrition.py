from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import get_user, log_food, get_day_nutrition, get_day_food_entries
from keyboards.keyboards import nutrition_menu, main_menu
from services.ai_service import parse_food, get_nutrition_advice, transcribe_voice
from services.scheduler import schedule_next_meal_reminder
from handlers.nav import send_nav
from states.states import FoodLogging

router = Router()


def today() -> str:
    return date.today().isoformat()


def nutrition_bar(current: float, goal: float, label: str, unit: str = "г") -> str:
    pct = min(current / goal * 100, 100) if goal else 0
    filled = int(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{label}: {bar} {current:.0f}/{goal:.0f}{unit} ({pct:.0f}%)"


@router.message(F.text == "🍽 Питание")
async def nutrition_section(message: Message):
    user = await get_user(message.from_user.id)
    totals = await get_day_nutrition(message.from_user.id, today())
    goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
             "carbs": user["goal_carbs"], "fat": user["goal_fat"]}

    remaining_kcal = goals["calories"] - totals["calories"]
    status = "✅ Цель выполнена!" if remaining_kcal <= 0 else f"До цели: {remaining_kcal:.0f} ккал"

    text = (
        f"🍽 <b>Питание на сегодня</b>\n\n"
        f"{nutrition_bar(totals['calories'], goals['calories'], '🔥 Калории', ' ккал')}\n"
        f"{nutrition_bar(totals['protein'], goals['protein'], '🥩 Белок')}\n"
        f"{nutrition_bar(totals['carbs'], goals['carbs'], '🌾 Углеводы')}\n"
        f"{nutrition_bar(totals['fat'], goals['fat'], '🫒 Жиры')}\n\n"
        f"{status}"
    )
    await send_nav(message, text, reply_markup=nutrition_menu())


@router.message(F.text.in_({"➕ Записать приём пищи", "➕ Записать еду"}))
async def ask_food(message: Message, state: FSMContext):
    await state.set_state(FoodLogging.waiting_input)
    await send_nav(
        message,
        "🍽 Напиши или надиктуй голосом что съел.\n\n"
        "<i>Примеры:</i>\n"
        "• <code>200г куриной грудки, 150г риса, огурец</code>\n"
        "• <code>творог 5% 200г, банан, кофе с молоком</code>\n"
        "• или отправь 🎤 голосовое сообщение",
    )


def _meal_icon(time_str: str) -> str:
    hour = int(time_str[:2])
    if hour < 10:
        return "🌅"
    if hour < 13:
        return "☀️"
    if hour < 17:
        return "🌤"
    if hour < 21:
        return "🌆"
    return "🌙"


@router.message(F.text == "🍴 Что съел сегодня")
async def food_detail(message: Message):
    user = await get_user(message.from_user.id)
    entries = await get_day_food_entries(message.from_user.id, today())
    totals = await get_day_nutrition(message.from_user.id, today())
    goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
             "carbs": user["goal_carbs"], "fat": user["goal_fat"]}

    if not entries:
        await send_nav(message, "📭 Сегодня ещё ничего не записано.\n\nНажми <b>➕ Записать еду</b>, чтобы добавить приём пищи.")
        return

    lines = [f"🍴 <b>Рацион за {today()}</b>\n"]
    for i, e in enumerate(entries, 1):
        time = e["created_at"][11:16]
        icon = _meal_icon(time)
        lines.append(
            f"{icon} <b>{i}. {e['description']}</b>\n"
            f"   🕐 {time}  ·  🔥 <b>{e['calories']:.0f} ккал</b>\n"
            f"   Б: <b>{e['protein']:.0f}г</b>  У: <b>{e['carbs']:.0f}г</b>  Ж: <b>{e['fat']:.0f}г</b>"
        )

    remaining = goals["calories"] - totals["calories"]
    cal_status = "✅ Цель выполнена!" if remaining <= 0 else f"ещё {remaining:.0f} ккал"

    prot_pct = min(totals['protein'] / goals['protein'] * 100, 100) if goals['protein'] else 0
    carb_pct = min(totals['carbs'] / goals['carbs'] * 100, 100) if goals['carbs'] else 0
    fat_pct = min(totals['fat'] / goals['fat'] * 100, 100) if goals['fat'] else 0

    lines.append(
        f"\n{'─' * 22}\n"
        f"📊 <b>Итого за день ({len(entries)} приём{'а' if 2 <= len(entries) <= 4 else 'ов' if len(entries) >= 5 else ''}):</b>\n"
        f"🔥 <b>{totals['calories']:.0f}</b> / {goals['calories']} ккал — {cal_status}\n"
        f"🥩 Белок:    <b>{totals['protein']:.0f}</b> / {goals['protein']}г ({prot_pct:.0f}%)\n"
        f"🌾 Углеводы: <b>{totals['carbs']:.0f}</b> / {goals['carbs']}г ({carb_pct:.0f}%)\n"
        f"🫒 Жиры:     <b>{totals['fat']:.0f}</b> / {goals['fat']}г ({fat_pct:.0f}%)"
    )

    await send_nav(message, "\n".join(lines))


@router.message(F.text == "📋 Итог за сегодня")
async def day_summary(message: Message):
    user = await get_user(message.from_user.id)
    entries = await get_day_food_entries(message.from_user.id, today())
    totals = await get_day_nutrition(message.from_user.id, today())
    goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
             "carbs": user["goal_carbs"], "fat": user["goal_fat"]}

    if not entries:
        await send_nav(message, "📭 Сегодня ещё ничего не записано.")
        return

    lines = [f"<b>Приёмы пищи за {today()}:</b>\n"]
    for e in entries:
        time = e["created_at"][11:16]
        lines.append(f"🕐 {time} — {e['description']}")
        lines.append(f"   {e['calories']:.0f} ккал · Б:{e['protein']:.0f} У:{e['carbs']:.0f} Ж:{e['fat']:.0f}")

    lines.append(f"\n<b>ИТОГО:</b>")
    lines.append(f"🔥 {totals['calories']:.0f} / {goals['calories']} ккал")
    lines.append(f"🥩 Белок: {totals['protein']:.0f} / {goals['protein']}г")
    lines.append(f"🌾 Углеводы: {totals['carbs']:.0f} / {goals['carbs']}г")
    lines.append(f"🫒 Жиры: {totals['fat']:.0f} / {goals['fat']}г")

    await send_nav(message, "\n".join(lines))


@router.message(F.text == "💡 Совет по питанию")
async def nutrition_tip(message: Message):
    user = await get_user(message.from_user.id)
    totals = await get_day_nutrition(message.from_user.id, today())
    goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
             "carbs": user["goal_carbs"], "fat": user["goal_fat"]}

    msg_id = await send_nav(message, "⏳ Анализирую питание...")
    advice = await get_nutrition_advice(totals, goals)
    try:
        await message.bot.edit_message_text(
            f"💡 {advice}", chat_id=message.chat.id, message_id=msg_id, parse_mode="HTML"
        )
    except Exception:
        await message.answer(f"💡 {advice}")


async def _process_food(message: Message, state: FSMContext, food_text: str, status_msg=None):
    """Общая логика: парсим текст еды и сохраняем."""
    await state.clear()
    user = await get_user(message.from_user.id)

    if status_msg is None:
        status_msg = await message.answer("⏳ Считаю КБЖУ...")

    try:
        result = await parse_food(food_text)
        await log_food(
            message.from_user.id, today(),
            result.get("description", food_text[:100]),
            result["calories"], result["protein"], result["carbs"], result["fat"]
        )

        totals = await get_day_nutrition(message.from_user.id, today())
        goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
                 "carbs": user["goal_carbs"], "fat": user["goal_fat"]}
        remaining = goals["calories"] - totals["calories"]

        await status_msg.edit_text(
            f"✅ <b>Записано:</b> {result.get('description', food_text[:80])}\n\n"
            f"🔥 {result['calories']:.0f} ккал · "
            f"Б: {result['protein']:.0f}г · "
            f"У: {result['carbs']:.0f}г · "
            f"Ж: {result['fat']:.0f}г\n\n"
            f"<b>За день итого:</b> {totals['calories']:.0f} / {goals['calories']} ккал\n"
            f"{'✅ Цель выполнена!' if remaining <= 0 else f'До цели: {remaining:.0f} ккал'}",
            parse_mode="HTML"
        )
        schedule_next_meal_reminder(message.from_user.id)
    except Exception as e:
        await status_msg.edit_text(f"❌ Не удалось распознать. Попробуй написать подробнее.\n<i>{e}</i>", parse_mode="HTML")


_NAV_BUTTONS = {
    "🏠 Главное меню", "💪 Тренировка", "🍽 Питание", "📊 Статистика", "⚙️ Настройки",
    "➕ Записать приём пищи", "➕ Записать еду", "📋 Итог за сегодня", "💡 Совет по питанию",
    "🍴 Что съел сегодня",
}


@router.message(
    FoodLogging.waiting_input,
    F.text,
    ~F.text.in_(_NAV_BUTTONS),
    ~F.text.startswith("/"),
    ~F.text.startswith("▶️"),
)
async def handle_food_text(message: Message, state: FSMContext):
    await _process_food(message, state, message.text)


@router.message(FoodLogging.waiting_input, F.voice)
async def handle_food_voice(message: Message, state: FSMContext):
    msg = await message.answer("🎤 Распознаю голос...")

    try:
        file = await message.bot.get_file(message.voice.file_id)
        audio_bytes = await message.bot.download_file(file.file_path)
        text = await transcribe_voice(audio_bytes.read(), "voice.ogg")
        await msg.edit_text(f"🎤 Распознано: <i>{text}</i>\n\n⏳ Считаю КБЖУ...", parse_mode="HTML")
        await _process_food(message, state, text, status_msg=msg)
    except Exception as e:
        await msg.edit_text(f"❌ Не удалось распознать голос: {e}")


@router.callback_query(F.data == "log_food")
async def cb_log_food(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FoodLogging.waiting_input)
    await callback.message.answer(
        "🍽 Напиши или надиктуй голосом что съел.\n\n"
        "<i>Примеры:</i>\n"
        "• <code>200г куриной грудки, 150г риса, огурец</code>\n"
        "• или отправь 🎤 голосовое сообщение",
        parse_mode="HTML",
    )
    await callback.answer()
