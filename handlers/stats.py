from aiogram import Router, F
from aiogram.types import Message
from datetime import date

from database.db import get_user, get_last_workouts, get_workout_sets, get_day_nutrition, get_user_day_types
from handlers.nav import send_nav

router = Router()

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


def _bar(current: float, goal: float) -> str:
    pct = min(current / goal * 100, 100) if goal else 0
    filled = int(pct / 10)
    return "█" * filled + "░" * (10 - filled)


@router.message(F.text == "📋 Сводка на сегодня")
async def today_summary(message: Message):
    user = await get_user(message.from_user.id)
    today = date.today().isoformat()

    # Питание
    totals = await get_day_nutrition(message.from_user.id, today)
    cal_goal = user["goal_calories"]
    prot_goal = user["goal_protein"]
    carb_goal = user["goal_carbs"]
    fat_goal = user["goal_fat"]

    remaining = cal_goal - totals["calories"]
    if remaining <= 0:
        cal_status = "✅ Цель выполнена!"
    else:
        cal_status = f"осталось {remaining:.0f} ккал"

    nutrition_block = (
        f"🍽 <b>Питание</b>\n"
        f"🔥 {_bar(totals['calories'], cal_goal)} {totals['calories']:.0f}/{cal_goal} ккал — {cal_status}\n"
        f"🥩 {_bar(totals['protein'], prot_goal)} {totals['protein']:.0f}/{prot_goal}г белок\n"
        f"🌾 {_bar(totals['carbs'], carb_goal)} {totals['carbs']:.0f}/{carb_goal}г углеводы\n"
        f"🫒 {_bar(totals['fat'], fat_goal)} {totals['fat']:.0f}/{fat_goal}г жиры"
    )

    # Тренировка сегодня
    workouts = await get_last_workouts(message.from_user.id, 1)
    if workouts and workouts[0]["date"] == today and workouts[0]["is_finished"]:
        w = workouts[0]
        sets = await get_workout_sets(w["id"])
        day_label = DAY_TYPES.get(w["day_type"], w["day_type"])
        week_label = WEEK_TYPES.get(w["week_type"], w["week_type"])
        workout_block = (
            f"💪 <b>Тренировка</b>\n"
            f"✅ {day_label} · {week_label}\n"
            f"🏋️ Тоннаж: <b>{w['total_tonnage']:.0f} кг</b> · RPE: <b>{w['avg_rpe']:.1f}</b>\n"
            f"Подходов записано: {len(sets)}"
        )
    else:
        # Следующий запланированный день
        week_type = user["current_week_type"]
        day_index = user["current_day_index"]
        day_types = await get_user_day_types(user["user_id"], week_type)
        if day_types:
            next_day = DAY_TYPES.get(day_types[day_index % len(day_types)], day_types[day_index % len(day_types)])
            next_week = WEEK_TYPES.get(week_type, week_type)
            workout_block = (
                f"💪 <b>Тренировка</b>\n"
                f"⏱ Сегодня тренировок нет\n"
                f"Следующий день: <b>{next_day}</b> · {next_week}"
            )
        else:
            workout_block = "💪 <b>Тренировка</b>\nПрограмма не настроена"

    await send_nav(
        message,
        f"📋 <b>Сводка на сегодня</b> — {today}\n\n{nutrition_block}\n\n{workout_block}"
    )


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    user = await get_user(message.from_user.id)
    workouts = await get_last_workouts(message.from_user.id, 10)

    lines = ["📊 <b>Статистика</b>\n"]

    # Питание за сегодня
    today = date.today().isoformat()
    totals = await get_day_nutrition(message.from_user.id, today)
    lines.append(f"<b>Питание сегодня:</b>")
    lines.append(f"🔥 {totals['calories']:.0f} / {user['goal_calories']} ккал")
    lines.append(f"🥩 Белок: {totals['protein']:.0f} / {user['goal_protein']}г\n")

    # Последние тренировки
    if workouts:
        lines.append(f"<b>Последние {len(workouts)} тренировок:</b>")
        for w in workouts:
            day_label = w["day_type"].replace("_", " ").title()
            lines.append(
                f"📅 {w['date']} · {day_label}\n"
                f"   🏋️ Тоннаж: {w['total_tonnage']:.0f}кг · RPE: {w['avg_rpe']:.1f}"
            )

        # Прогресс тоннажа
        if len(workouts) >= 2:
            first = workouts[-1]["total_tonnage"]
            last = workouts[0]["total_tonnage"]
            diff = last - first
            sign = "+" if diff >= 0 else ""
            lines.append(f"\n📈 Тоннаж за период: {sign}{diff:.0f}кг")
    else:
        lines.append("Тренировок пока нет.")

    await send_nav(message, "\n".join(lines))
