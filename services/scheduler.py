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
    logger.info("Напоминание о еде → user_id=%s", user_id)
    if await was_food_logged_recently(user_id, minutes=30):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ Записать еду", callback_data="log_food")
    ]])
    try:
        await _bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.warning("Не удалось отправить напоминание %s: %s", user_id, e)


def setup_daily_reminders(user_id: int, user_meals: list[dict] = None, utc_offset: int = 7):
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
        utc_hour = (meal["hour"] - utc_offset) % 24
        _scheduler.add_job(
            _send_meal_reminder,
            "cron",
            hour=utc_hour,
            minute=meal["minute"],
            args=[user_id, _MEAL_TEXTS.get(meal_id, "🍽 Время записать приём пищи!")],
            id=job_id,
            replace_existing=True,
            timezone="UTC",
        )
    logger.info("Напоминания настроены для user_id=%s (UTC+%s)", user_id, utc_offset)


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
            if not user.get("notify_weekly_report", 1):
                continue
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
    logger.info("Напоминание о тренировке → user_id=%s", user_id)
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


def setup_workout_reminder(user_id: int, hour: int = 17, minute: int = 0, utc_offset: int = 7):
    """Регистрирует ежедневное напоминание о тренировке для пользователя."""
    if _scheduler is None:
        return
    job_id = f"workout_{user_id}"
    utc_hour = (hour - utc_offset) % 24
    _scheduler.add_job(
        _send_workout_reminder,
        "cron",
        hour=utc_hour,
        minute=minute,
        args=[user_id],
        id=job_id,
        replace_existing=True,
        timezone="UTC",
    )


async def _send_morning_brief(user_id: int):
    from database.db import (get_user, get_user_program, get_user_day_types,
                              get_day_nutrition, get_last_workouts, get_week_workout_count,
                              get_nutrition_week_avg)
    from services.ai_service import get_morning_tip, get_food_idea
    from datetime import datetime, timedelta as td, timezone
    if _bot is None:
        return
    logger.info("Утренний бриф → user_id=%s", user_id)
    user = await get_user(user_id)
    if not user or not user.get("notify_morning_brief", 1):
        return

    utc_offset = user.get("utc_offset", 7)
    tz = timezone(td(hours=utc_offset))
    now_local = datetime.now(tz)
    today_str = now_local.date().isoformat()
    yesterday_str = (now_local.date() - td(days=1)).isoformat()

    week_type = user.get("current_week_type", "strength")
    day_index = user.get("current_day_index", 0)
    day_types = await get_user_day_types(user_id, week_type)
    if not day_types:
        return

    day_type = day_types[day_index % len(day_types)]
    exercises = await get_user_program(user_id, week_type, day_type)

    WEEK_LABELS = {"strength": "Силовая", "volume": "Объёмная", "deload": "Разгрузочная"}
    DAY_LABELS = {"upper_strength": "Верх — Сила", "upper_volume": "Верх — Объём", "legs": "Ноги"}
    week_label = WEEK_LABELS.get(week_type, week_type)
    day_label = DAY_LABELS.get(day_type, day_type.replace("_", " ").title())

    name = user.get("name", "").split()[0] if user.get("name") else "Привет"
    lines = [f"🌅 <b>Доброе утро, {name}!</b>\n"]

    # ── 💪 План тренировки ────────────────────────────────────────────────────
    if user.get("brief_workout", 1):
        if exercises:
            lines.append(f"💪 <b>Сегодня: {day_label}</b> · {week_label}")
            for ex in exercises[:6]:
                w = ex["weight"]
                w_str = f"{int(w) if w == int(w) else w}кг" if w > 0 else "св.вес"
                lines.append(f"  • {ex['exercise']}: {w_str} × {ex['reps_range']} ({ex['sets']} подх.)")
            if len(exercises) > 6:
                lines.append(f"  <i>...ещё {len(exercises) - 6} упражнений</i>")
        else:
            lines.append("😴 <b>Сегодня день отдыха</b> — восстанавливайся!")

    # ── 📊 Итоги вчера ────────────────────────────────────────────────────────
    if user.get("brief_yesterday", 1):
        try:
            yest = await get_day_nutrition(user_id, yesterday_str)
            if yest["calories"] > 0:
                g_cal = user.get("goal_calories", 1)
                pct = int(yest["calories"] / g_cal * 100) if g_cal else 0
                icon = "✅" if pct >= 90 else ("⚠️" if pct >= 70 else "❌")
                lines.append(
                    f"\n📊 <b>Вчера:</b> {icon} {yest['calories']:.0f} ккал ({pct}% цели) · "
                    f"Б: {yest['protein']:.0f}г"
                )
        except Exception:
            pass

    # ── 🥩 Нутриент-акцент ────────────────────────────────────────────────────
    if user.get("brief_nutrient", 1):
        try:
            week_avg = await get_nutrition_week_avg(user_id)
            g_prot = user.get("goal_protein", 1)
            g_carb = user.get("goal_carbs", 1)
            g_fat = user.get("goal_fat", 1)
            if week_avg and g_prot:
                prot_pct = week_avg.get("protein", 0) / g_prot * 100
                carb_pct = week_avg.get("carbs", 0) / g_carb * 100 if g_carb else 100
                fat_pct = week_avg.get("fat", 0) / g_fat * 100 if g_fat else 100
                low = min(
                    [("белок", prot_pct, user.get("goal_protein", 0)),
                     ("углеводы", carb_pct, user.get("goal_carbs", 0)),
                     ("жиры", fat_pct, user.get("goal_fat", 0))],
                    key=lambda x: x[1]
                )
                if low[1] < 80:
                    deficit_g = int(low[2] * (1 - low[1] / 100))
                    lines.append(f"🥩 <b>Акцент:</b> {low[0]} — недобираешь ~{deficit_g}г/день за эту неделю")
        except Exception:
            pass

    # ── 😴 Статус восстановления ──────────────────────────────────────────────
    if user.get("brief_recovery", 1):
        try:
            last_workouts = await get_last_workouts(user_id, limit=1)
            if last_workouts:
                rpe = last_workouts[0].get("avg_rpe", 0)
                if rpe >= 8.5:
                    lines.append("😴 <b>Восстановление:</b> последняя тренировка была тяжёлой — не форсируй")
                elif rpe >= 7.0:
                    lines.append("💪 <b>Восстановление:</b> готов к нормальной нагрузке")
                else:
                    lines.append("🔋 <b>Восстановление:</b> хорошо восстановился — можно жать на полную")
        except Exception:
            pass

    # ── 📈 Прогресс недели ────────────────────────────────────────────────────
    if user.get("brief_week_prog", 1):
        try:
            days_since_monday = now_local.weekday()
            monday_str = (now_local.date() - td(days=days_since_monday)).isoformat()
            done = await get_week_workout_count(user_id, monday_str)
            planned = user.get("days_per_week", 3)
            remaining = max(0, planned - done)
            if done > 0 or remaining > 0:
                bar = "🟩" * done + "⬜" * remaining
                lines.append(f"📈 <b>Неделя:</b> {bar} {done}/{planned} тренировок")
        except Exception:
            pass

    # ── 🍽 КБЖУ цели ─────────────────────────────────────────────────────────
    lines.append(
        f"\n🍽 <b>Цели на сегодня:</b>\n"
        f"🔥 {user.get('goal_calories', 0)} ккал  "
        f"🥩 {user.get('goal_protein', 0)}г белка  "
        f"🌾 {user.get('goal_carbs', 0)}г углев."
    )

    # ── 🍳 Идея еды ───────────────────────────────────────────────────────────
    if user.get("brief_food_idea", 0):
        try:
            idea = await get_food_idea(
                user.get("goal_calories", 0),
                user.get("goal_protein", 0),
                user.get("goal_carbs", 0),
                user.get("goal_fat", 0),
                "завтрак",
            )
            lines.append(f"\n🍳 <b>Идея завтрака:</b>\n<i>{idea}</i>")
        except Exception:
            pass

    # ── 💧 Норма воды ─────────────────────────────────────────────────────────
    if user.get("brief_water", 1):
        water_goal = user.get("water_goal", 8)
        lines.append(f"💧 Норма воды: <b>{water_goal} стаканов</b> ({water_goal * 250} мл)")

    # ── 💡 Совет дня ──────────────────────────────────────────────────────────
    if user.get("brief_tip", 1):
        try:
            tip = await get_morning_tip(user, bool(exercises), week_label)
            lines.append(f"\n💡 <i>{tip}</i>")
        except Exception:
            pass

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💪 Начать тренировку", callback_data="go_workout"),
        InlineKeyboardButton(text="➕ Записать еду", callback_data="log_food"),
    ]])

    try:
        await _bot.send_message(user_id, "\n".join(lines), parse_mode="HTML",
                                reply_markup=kb if exercises else None)
    except Exception as e:
        logger.warning("Morning brief failed for %s: %s", user_id, e)


def setup_morning_brief(user_id: int, hour: int = 8, minute: int = 0, utc_offset: int = 7):
    """Регистрирует ежедневный утренний бриф для пользователя."""
    if _scheduler is None:
        return
    job_id = f"morning_brief_{user_id}"
    utc_hour = (hour - utc_offset) % 24
    _scheduler.add_job(
        _send_morning_brief,
        "cron",
        hour=utc_hour,
        minute=minute,
        args=[user_id],
        id=job_id,
        replace_existing=True,
        timezone="UTC",
    )


def remove_morning_brief(user_id: int):
    if _scheduler is None:
        return
    job_id = f"morning_brief_{user_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


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
