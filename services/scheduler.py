"""Планировщик ежедневных напоминаний о приёмах пищи."""
import logging
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.db import was_food_logged_recently, was_workout_done_today

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None
_bot: Bot = None

MEALS = [
    {"id": "breakfast", "hour": 8,  "minute": 30, "text": "🍳 <b>Завтракал?</b>\nЗапиши что съел, пока не забыл!"},
    {"id": "snack1",    "hour": 11, "minute": 30, "text": "🍎 <b>Время перекуса</b>\nЗапиши если что-то съел!"},
    {"id": "lunch",     "hour": 13, "minute": 30, "text": "🍱 <b>Обедал?</b>\nЗафиксируй обед — это важно для калорий!"},
    {"id": "snack2",    "hour": 16, "minute": 30, "text": "🥜 <b>Полдник</b>\nПерекусил? Запиши!"},
    {"id": "dinner",    "hour": 19, "minute": 30, "text": "🍽 <b>Ужин</b>\nЗапиши ужин, чтобы закрыть день!"},
]

_MEAL_TEXTS = {m["id"]: m["text"] for m in MEALS}


async def _send_meal_reminder(user_id: int, text: str):
    if _bot is None:
        return
    # Не беспокоим, если человек уже что-то записал за последние 30 минут
    if await was_food_logged_recently(user_id, minutes=30):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ Записать еду", callback_data="log_food")
    ]])
    try:
        await _bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.warning("Не удалось отправить напоминание %s: %s", user_id, e)


def setup_daily_reminders(user_id: int, user_meals: list[dict] = None):
    """Регистрирует cron-напоминания для пользователя по его настройкам из БД."""
    if _scheduler is None:
        return
    meals = user_meals if user_meals is not None else [
        {"meal_id": m["id"], "enabled": 1, "hour": m["hour"], "minute": m["minute"]}
        for m in MEALS
    ]
    for meal in meals:
        meal_id = meal["meal_id"]
        job_id = f"meal_{user_id}_{meal_id}"
        if not meal.get("enabled", 1):
            if _scheduler.get_job(job_id):
                _scheduler.remove_job(job_id)
            continue
        _scheduler.add_job(
            _send_meal_reminder,
            "cron",
            hour=meal["hour"],
            minute=meal["minute"],
            args=[user_id, _MEAL_TEXTS.get(meal_id, "🍽 Время записать приём пищи!")],
            id=job_id,
            replace_existing=True,
            timezone="Asia/Krasnoyarsk",
        )
    logger.info("Напоминания настроены для user_id=%s", user_id)


def remove_daily_reminders(user_id: int):
    """Удаляет все напоминания пользователя."""
    if _scheduler is None:
        return
    for meal in MEALS:
        job_id = f"meal_{user_id}_{meal['id']}"
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)


async def _send_weekly_report():
    from database.db import (get_all_onboarded_users, get_user,
                              get_week_workouts, get_week_nutrition_avg, get_week_exercise_weights,
                              get_weekly_new_prs, get_weekly_kbju_days_in_norm)
    if _bot is None:
        return

    today = date.today()
    week_end = today.isoformat()
    week_start = (today - timedelta(days=6)).isoformat()
    prev_start = (today - timedelta(days=13)).isoformat()
    prev_end   = (today - timedelta(days=7)).isoformat()

    for user_id in await get_all_onboarded_users():
        try:
            user = await get_user(user_id)
            workouts = await get_week_workouts(user_id, week_start, week_end)
            nutrition = await get_week_nutrition_avg(user_id, week_start, week_end)
            cur_weights = await get_week_exercise_weights(user_id, week_start, week_end)
            prev_weights = await get_week_exercise_weights(user_id, prev_start, prev_end)
            new_prs = await get_weekly_new_prs(user_id, week_start, week_end)
            kbju_days = await get_weekly_kbju_days_in_norm(user_id, week_start, week_end)

            if len(workouts) == 0 and nutrition["days_tracked"] == 0:
                await _bot.send_message(
                    user_id,
                    "📋 <b>Итоги недели</b>\n\nНи одной тренировки и записей питания — начни новую неделю с понедельника! 💪",
                    parse_mode="HTML",
                )
                continue

            lines = [f"📋 <b>Итоги недели</b> — {week_start[5:].replace('-', '.')}–{week_end[5:].replace('-', '.')}\n"]

            # Тренировки
            tonnage = sum(w["total_tonnage"] for w in workouts)
            prev_workouts = await get_week_workouts(user_id, prev_start, prev_end)
            prev_tonnage = sum(w["total_tonnage"] for w in prev_workouts)
            diff_t = tonnage - prev_tonnage
            sign = "+" if diff_t >= 0 else ""
            lines.append(
                f"💪 <b>Тренировок:</b> {len(workouts)}\n"
                f"🏋️ Тоннаж: <b>{tonnage:,.0f} кг</b>"
                + (f" ({sign}{diff_t:.0f} кг vs пред. нед.)" if prev_tonnage > 0 else "")
            )

            # Личные рекорды
            if new_prs:
                pr_lines = "\n".join(f"  🏆 {p['exercise']}: {p['weight']:.0f} кг" for p in new_prs[:5])
                lines.append(f"\n🎯 <b>Новые рекорды:</b>\n{pr_lines}")

            # Прогресс весов (без новых ПР)
            pr_exercises = {p["exercise"] for p in new_prs}
            gains = []
            for ex, w_new in cur_weights.items():
                if ex in pr_exercises:
                    continue
                w_old = prev_weights.get(ex)
                if w_old and w_new > w_old:
                    gains.append(f"  ↗ {ex}: {w_old:.0f} → {w_new:.0f} кг")
            if gains:
                lines.append("\n📈 <b>Прогресс:</b>\n" + "\n".join(gains))

            # Питание
            if nutrition["days_tracked"] > 0:
                cal_pct = int(nutrition["avg_calories"] / user["goal_calories"] * 100) if user["goal_calories"] else 0
                prot_pct = int(nutrition["avg_protein"] / user["goal_protein"] * 100) if user["goal_protein"] else 0
                norm_icon = "✅" if kbju_days >= 5 else "🟡" if kbju_days >= 3 else "🔴"
                lines.append(
                    f"\n🍽 <b>Питание</b> (ср. за {nutrition['days_tracked']} дн.):\n"
                    f"🔥 {nutrition['avg_calories']:.0f} / {user['goal_calories']} ккал ({cal_pct}%)\n"
                    f"🥩 Белок: {nutrition['avg_protein']:.0f} / {user['goal_protein']}г ({prot_pct}%)\n"
                    f"🌾 Углев.: {nutrition['avg_carbs']:.0f} г  🫒 Жиры: {nutrition['avg_fat']:.0f} г\n"
                    f"{norm_icon} Дней в норме (±20%): <b>{kbju_days}/7</b>"
                )

            await _bot.send_message(user_id, "\n".join(lines), parse_mode="HTML")
        except Exception as e:
            logger.warning("Weekly report failed for user %s: %s", user_id, e)


async def _send_workout_reminder(user_id: int):
    from database.db import get_user, get_active_workout
    from datetime import date, timedelta, timezone, timedelta as td
    if _bot is None:
        return
    user = await get_user(user_id)
    if not user:
        return
    utc_offset = user.get("utc_offset", 7)
    local_date = (date.today() + td(hours=utc_offset)).isoformat() if utc_offset else date.today().isoformat()
    if await was_workout_done_today(user_id, local_date):
        return
    active = await get_active_workout(user_id)
    if active:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💪 Начать тренировку", callback_data="go_workout")
    ]])
    try:
        await _bot.send_message(
            user_id,
            "💪 <b>Время тренироваться!</b>\n\nСегодня день тренировки — не пропускай, прогресс делается стабильностью.",
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception as e:
        logger.warning("Не удалось отправить напоминание о тренировке %s: %s", user_id, e)


def setup_workout_reminder(user_id: int, hour: int = 17, minute: int = 0):
    """Регистрирует ежедневное напоминание о тренировке для пользователя."""
    if _scheduler is None:
        return
    job_id = f"workout_{user_id}"
    _scheduler.add_job(
        _send_workout_reminder,
        "cron",
        hour=hour,
        minute=minute,
        args=[user_id],
        id=job_id,
        replace_existing=True,
        timezone="Asia/Krasnoyarsk",
    )


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    global _scheduler, _bot
    _bot = bot
    _scheduler = AsyncIOScheduler(timezone="Asia/Krasnoyarsk")
    _scheduler.add_job(
        _send_weekly_report,
        "cron",
        day_of_week="sun",
        hour=20,
        minute=0,
        id="weekly_report",
        replace_existing=True,
    )
    return _scheduler
