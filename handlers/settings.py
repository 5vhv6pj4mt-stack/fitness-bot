from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database.db import get_user, update_user
from keyboards.keyboards import main_menu
from states.states import Setup
from handlers.nav import send_nav

router = Router()


@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    user = await get_user(message.from_user.id)
    goal_labels = {"mass": "Набор массы", "loss": "Похудение", "strength": "Сила", "tone": "Тонус"}
    await send_nav(
        message,
        f"⚙️ <b>Твои настройки</b>\n\n"
        f"👤 Имя: {user.get('name', '—')}\n"
        f"⚖️ Вес: {user.get('weight', '—')} кг\n"
        f"📏 Рост: {user.get('height', '—')} см\n"
        f"🎂 Возраст: {user.get('age', '—')} лет\n"
        f"🎯 Цель: {goal_labels.get(user.get('goal', ''), '—')}\n"
        f"📅 Дней в неделю: {user.get('days_per_week', '—')}\n\n"
        f"<b>Цели по питанию:</b>\n"
        f"🔥 {user.get('goal_calories', 0)} ккал\n"
        f"🥩 Белок: {user.get('goal_protein', 0)}г\n"
        f"🌾 Углеводы: {user.get('goal_carbs', 0)}г\n"
        f"🫒 Жиры: {user.get('goal_fat', 0)}г\n\n"
        f"Чтобы обновить вес — напиши: <code>вес 75</code>\n"
        f"Чтобы переделать программу — напиши /start",
    )


@router.message(F.text.lower().startswith("вес "))
async def update_weight(message: Message):
    try:
        weight = float(message.text.split()[1].replace(",", "."))
        await update_user(message.from_user.id, weight=weight)
        await message.answer(f"✅ Вес обновлён: {weight} кг")
    except (ValueError, IndexError):
        await message.answer("Формат: <code>вес 75.5</code>", parse_mode="HTML")
