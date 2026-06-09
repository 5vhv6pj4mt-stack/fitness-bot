from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from database.db import create_user, update_user, get_user, save_user_program
from services.scheduler import setup_daily_reminders, setup_workout_reminder
from services.ai_service import generate_program
from states.states import Onboarding

# Пользователи с готовой программой — загружаем из program_data.py, не генерируем AI
PRESET_PROGRAM_USERS = {
    311739548: {  # Кирилл
        "week": 16,
        "week_type": "volume",
        "day_index": 2,
        "calories": 3300,
        "protein": 160,
        "carbs": 380,
        "fat": 90,
    }
}

router = Router()

GOALS = {
    "💪 Набор массы": "mass",
    "🔥 Похудение": "loss",
    "🏋️ Сила": "strength",
    "🌿 Общий тонус": "tone",
}

EXPERIENCE = {
    "🌱 Новичок (до 1 года)": "beginner",
    "💪 Средний (1–3 года)": "intermediate",
    "🔥 Продвинутый (3+ лет)": "advanced",
}

EQUIPMENT = {
    "🏋️ Полный зал": "gym",
    "🏠 Дома (гантели, турник)": "home",
    "🤸 Без оборудования": "minimal",
}


def kb(buttons: list[str], cols: int = 2) -> ReplyKeyboardMarkup:
    rows = [buttons[i:i+cols] for i in range(0, len(buttons), cols)]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in rows],
        resize_keyboard=True
    )


async def start_onboarding(message: Message, state: FSMContext):
    name = message.from_user.first_name or "друг"
    await state.update_data(name=name)
    await state.set_state(Onboarding.age)
    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        "Я <b>Стать</b> — твой помощник по тренировкам и питанию.\n\n"
        "Давай составим твой персональный план. Это займёт 1 минуту.\n\n"
        "Сколько тебе лет?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(Onboarding.age)
async def ob_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
        if not 10 <= age <= 80:
            raise ValueError
        await state.update_data(age=age)
        await state.set_state(Onboarding.weight)
        await message.answer("Твой текущий вес (кг)? Например: <code>75</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("Введи корректный возраст, например: <code>25</code>", parse_mode="HTML")


@router.message(Onboarding.weight)
async def ob_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
        await state.update_data(weight=weight)
        await state.set_state(Onboarding.height)
        await message.answer("Твой рост (см)? Например: <code>178</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("Введи число, например: <code>75.5</code>", parse_mode="HTML")


@router.message(Onboarding.height)
async def ob_height(message: Message, state: FSMContext):
    try:
        height = float(message.text.replace(",", "."))
        await state.update_data(height=height)
        await state.set_state(Onboarding.goal)
        await message.answer(
            "Какая твоя основная цель?",
            reply_markup=kb(list(GOALS.keys()))
        )
    except ValueError:
        await message.answer("Введи число, например: <code>178</code>", parse_mode="HTML")


@router.message(Onboarding.goal)
async def ob_goal(message: Message, state: FSMContext):
    goal = GOALS.get(message.text)
    if not goal:
        await message.answer("Выбери один из вариантов 👆")
        return
    await state.update_data(goal=goal)
    await state.set_state(Onboarding.experience)
    await message.answer(
        "Какой у тебя опыт тренировок?",
        reply_markup=kb(list(EXPERIENCE.keys()), cols=1)
    )


@router.message(Onboarding.experience)
async def ob_experience(message: Message, state: FSMContext):
    exp = EXPERIENCE.get(message.text)
    if not exp:
        await message.answer("Выбери один из вариантов 👆")
        return
    await state.update_data(experience=exp)
    await state.set_state(Onboarding.days)
    await message.answer(
        "Сколько дней в неделю готов тренироваться?",
        reply_markup=kb(["2 дня", "3 дня", "4 дня", "5 дней"])
    )


@router.message(Onboarding.days)
async def ob_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.split()[0])
        if not 1 <= days <= 7:
            raise ValueError
        await state.update_data(days_per_week=days)
        await state.set_state(Onboarding.equipment)
        await message.answer(
            "Какое оборудование доступно?",
            reply_markup=kb(list(EQUIPMENT.keys()), cols=1)
        )
    except (ValueError, IndexError):
        await message.answer("Выбери один из вариантов 👆")


@router.message(Onboarding.equipment)
async def ob_equipment(message: Message, state: FSMContext):
    equip = EQUIPMENT.get(message.text)
    if not equip:
        await message.answer("Выбери один из вариантов 👆")
        return
    await state.update_data(equipment=equip)
    await state.set_state(Onboarding.injuries)
    await message.answer(
        "Есть ли травмы, боли или хронические заболевания, которые нужно учесть?\n\n"
        "<i>Если нет — напиши «нет»</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Нет")]],
            resize_keyboard=True
        )
    )


@router.message(Onboarding.injuries)
async def ob_injuries(message: Message, state: FSMContext):
    injuries = None if message.text.lower() in ("нет", "no", "-") else message.text.strip()
    await state.update_data(injuries=injuries)

    data = await state.get_data()
    await state.clear()

    # Создаём или обновляем пользователя
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id, data["name"])

    await update_user(
        message.from_user.id,
        name=data["name"],
        age=data["age"],
        weight=data["weight"],
        height=data["height"],
        goal=data["goal"],
        experience=data["experience"],
        days_per_week=data["days_per_week"],
        equipment=data["equipment"],
        injuries=injuries,
    )

    goal_labels = {
        "mass": "набор массы", "loss": "похудение",
        "strength": "сила", "tone": "тонус"
    }

    preset = PRESET_PROGRAM_USERS.get(message.from_user.id)

    if preset:
        # Загружаем готовую программу из program_data.py
        await message.answer(
            f"✅ <b>Данные сохранены!</b>\n\n"
            f"👤 {data['name']}, {data['age']} лет · {data['weight']} кг\n\n"
            f"📂 Загружаю твою программу тренировок...",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        try:
            from database.program_data import PROGRAM
            program_flat = []
            for week_type, days in PROGRAM.items():
                for day_type, exercises in days.items():
                    for i, ex in enumerate(exercises):
                        program_flat.append({
                            "week_type": week_type,
                            "day_type": day_type,
                            "order_num": i,
                            "exercise": ex["exercise"],
                            "sets": ex["sets"],
                            "reps_range": ex["reps"],
                            "weight": ex["weight"],
                            "rpe_range": ex["rpe"],
                            "rest": ex["rest"],
                        })

            await save_user_program(message.from_user.id, program_flat)
            await update_user(
                message.from_user.id,
                goal_calories=preset["calories"],
                goal_protein=preset["protein"],
                goal_carbs=preset["carbs"],
                goal_fat=preset["fat"],
                current_week=preset["week"],
                current_week_type=preset["week_type"],
                current_day_index=preset["day_index"],
                onboarded=1,
            )
            setup_daily_reminders(message.from_user.id)
            setup_workout_reminder(message.from_user.id)

            await message.answer(
                f"✅ <b>Программа загружена!</b>\n\n"
                f"📅 Неделя {preset['week']} · {preset['week_type'].capitalize()}\n"
                f"🔥 Цель: {preset['calories']} ккал · 🥩 {preset['protein']}г белка\n\n"
                f"Жми <b>Тренировка</b> чтобы начать!",
                parse_mode="HTML"
            )
        except Exception as e:
            await message.answer(f"⚠️ Ошибка загрузки программы: {e}")
    else:
        # Генерируем программу через AI
        await message.answer(
            f"✅ <b>Данные сохранены!</b>\n\n"
            f"👤 {data['name']}, {data['age']} лет\n"
            f"⚖️ {data['weight']} кг · 📏 {data['height']} см\n"
            f"🎯 Цель: {goal_labels.get(data['goal'])}\n\n"
            f"⏳ Генерирую персональную программу...\n"
            f"<i>Это займёт 10–20 секунд</i>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        try:
            user_data = await get_user(message.from_user.id)
            program, nutrition = await generate_program(user_data)

            await save_user_program(message.from_user.id, program)

            week_types = list(dict.fromkeys(ex["week_type"] for ex in program))

            await update_user(
                message.from_user.id,
                goal_calories=nutrition["calories"],
                goal_protein=nutrition["protein"],
                goal_carbs=nutrition["carbs"],
                goal_fat=nutrition["fat"],
                current_week=1,
                current_week_type=week_types[0],
                current_day_index=0,
                onboarded=1,
            )
            setup_daily_reminders(message.from_user.id)
            setup_workout_reminder(message.from_user.id)

            await message.answer(
                f"🎉 <b>Программа готова!</b>\n\n"
                f"<b>Питание (суточные цели):</b>\n"
                f"🔥 {nutrition['calories']} ккал\n"
                f"🥩 Белок: {nutrition['protein']}г\n"
                f"🌾 Углеводы: {nutrition['carbs']}г\n"
                f"🫒 Жиры: {nutrition['fat']}г\n\n"
                f"<i>{nutrition.get('comment', '')}</i>\n\n"
                f"💪 Жми <b>Тренировка</b> чтобы начать!",
                parse_mode="HTML"
            )
        except Exception as e:
            await message.answer(
                f"⚠️ Не удалось сгенерировать программу: {e}\n\n"
                "Попробуй ещё раз через /start"
            )

    from handlers.main_menu import show_main
    user_data = await get_user(message.from_user.id)
    if user_data and user_data.get("onboarded"):
        await show_main(message, user_data)
