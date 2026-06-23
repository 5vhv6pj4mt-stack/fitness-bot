from datetime import date as dt_date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database.db import get_user, create_user, update_user, get_day_nutrition, get_last_workouts, reset_user_cycle, delete_user_program, save_user_program
from keyboards.keyboards import main_menu, WEBAPP_URL
from services.ai_service import generate_program


router = Router()

DAY_LABELS = {
    "upper_strength": "Верх — Сила",
    "upper_volume": "Верх — Объём",
    "legs": "Ноги",
}
WEEK_LABELS = {
    "strength": "Силовая",
    "volume": "Объёмная",
    "deload": "Разгрузочная",
}
WEEK_DESC = {
    "strength": "Максимальные веса, малый объём",
    "volume": "Больше подходов, умеренный вес",
    "deload": "↓ Объём снижен, акцент на технику",
}
DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
             "июля", "августа", "сентября", "октября", "ноября", "декабря"]


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    if not user or not user.get("onboarded"):
        from handlers.onboarding import start_onboarding
        await start_onboarding(message, state)
    else:
        await show_main(message, user)


async def show_main(message: Message, user: dict, use_nav: bool = False):
    from database.db import get_user_day_types
    today = dt_date.today()
    week_type = user.get("current_week_type", "strength")
    day_index = user.get("current_day_index", 0)

    day_types = await get_user_day_types(user["user_id"], week_type)
    if day_types:
        day_type = day_types[day_index % len(day_types)]
        day_label = DAY_LABELS.get(day_type, day_type.replace("_", " ").title())
    else:
        day_label = None

    week_label = WEEK_LABELS.get(week_type, week_type.capitalize())

    # Одна строка питания
    totals = await get_day_nutrition(user["user_id"], today.isoformat())
    goal_cal = user.get("goal_calories") or 3300
    cal_pct = min(totals["calories"] / goal_cal * 100, 100) if goal_cal else 0
    nutrition_line = f"🔥 {totals['calories']:.0f} / {goal_cal} ккал ({cal_pct:.0f}%)"

    # Одна строка тренировки
    workouts = await get_last_workouts(user["user_id"], 1)
    if workouts and dt_date.fromisoformat(workouts[0]["date"]) == today:
        workout_line = f"💪 Тренировка сегодня ✅"
    elif day_label:
        workout_line = f"💪 Следующий день: <b>{day_label}</b> · {week_label}"
    else:
        workout_line = "💪 Программа не настроена"

    date_str = f"{DAYS_RU[today.weekday()]}, {today.day} {MONTHS_RU[today.month - 1]}"

    text = (
        f"🏠 <b>Главное меню</b>  {date_str}\n\n"
        f"{nutrition_line}\n"
        f"{workout_line}"
    )

    kb = main_menu(day_label=day_label, week_label=week_label)
    if use_nav:
        from handlers.nav import send_nav
        await send_nav(message, text, reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

    await _ensure_pinned(message, user)


async def _ensure_pinned(message: Message, user: dict):
    """Отправляет и закрепляет сообщение-шорткат с кнопкой мини-приложения.
    Делает это один раз — id закреплённого сообщения хранится в users.pinned_msg_id."""
    if user.get("pinned_msg_id"):
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    try:
        sent = await message.answer(
            "👆 Нажми чтобы открыть приложение",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🏋️ Открыть Стать",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]])
        )
        await message.bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=sent.message_id,
            disable_notification=True,
        )
        await update_user(user["user_id"], pinned_msg_id=sent.message_id)
    except Exception:
        pass


@router.message(F.text == "🏠 Главное меню")
async def go_main(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    if user:
        await show_main(message, user, use_nav=True)


@router.message(Command("workout"))
async def cmd_workout(message: Message, state: FSMContext):
    from handlers.workout import workout_section
    await workout_section(message, state)


@router.message(Command("food"))
async def cmd_food(message: Message, state: FSMContext):
    from handlers.nutrition import ask_food
    await ask_food(message, state)


@router.message(Command("summary"))
async def cmd_summary(message: Message):
    from handlers.stats import today_summary
    await today_summary(message)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    from handlers.stats import show_stats
    await show_stats(message)


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    from handlers.settings import settings_menu
    await settings_menu(message)


@router.message(Command("reset"))
async def cmd_reset(message: Message):
    user_id = message.from_user.id

    try:
        user = await get_user(user_id)

        if not user or user.get("onboarded") != 1:
            await message.answer("Сначала пройди онбординг — используй /start")
            return

        await message.answer("⏳ Перегенерирую программу, подожди...")

        # Сначала генерируем — если упадёт, старая программа останется
        program, nutrition = await generate_program(user)

        await reset_user_cycle(user_id)
        await delete_user_program(user_id)
        await save_user_program(user_id, program)
        if nutrition:
            await update_user(user_id,
                              goal_calories=nutrition.get("calories"),
                              goal_protein=nutrition.get("protein"),
                              goal_carbs=nutrition.get("carbs"),
                              goal_fat=nutrition.get("fat"))

        user_updated = await get_user(user_id)
        kb = main_menu(
            day_label=None,
            week_label=WEEK_LABELS.get(
                user_updated.get("current_week_type", "strength") if user_updated else "strength",
                "Силовая"
            )
        )

        await message.answer(
            "✅ Программа пересоздана! Цикл начат заново с недели 1.",
            reply_markup=kb
        )

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при сбросе цикла: {e}")