import asyncio
import io
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from database.db import (get_user, get_last_workouts, get_workout_sets, get_day_nutrition,
                         get_user_day_types, get_last_workouts_rich, get_all_time_stats,
                         get_exercise_prs, get_nutrition_week_avg,
                         get_top_exercises, get_exercise_history,
                         get_best_sets_for_1rm, get_muscle_volume,
                         get_tonnage_by_weeks)
from handlers.nav import send_nav, track_msg
from handlers.nutrition import user_today
from keyboards.keyboards import main_menu

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


async def generate_tonnage_chart(data: list[dict]) -> io.BytesIO:
    labels = []
    values = []
    for i, item in enumerate(data, start=1):
        week_label = item.get("week_label") or item.get("date") or f"Нед {i}"
        try:
            if len(week_label) == 10 and week_label[4] == "-":
                parts = week_label.split("-")
                week_label = f"{parts[2]}.{parts[1]}"
        except Exception:
            pass
        labels.append(week_label)
        values.append(float(item.get("tonnage", 0)))

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.9), 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    bars = ax.bar(labels, values, color="#4CAF50", edgecolor="#388E3C", linewidth=0.8)

    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.01,
                f"{val:,.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#e0e0e0",
                fontweight="bold",
            )

    ax.set_title("Тоннаж по неделям", color="#e0e0e0", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Период", color="#9e9e9e", fontsize=9)
    ax.set_ylabel("Тоннаж (кг)", color="#9e9e9e", fontsize=9)
    ax.tick_params(colors="#9e9e9e", labelsize=8)
    ax.yaxis.get_offset_text().set_color("#9e9e9e")

    for spine in ax.spines.values():
        spine.set_color("#2d2d4e")

    ax.grid(True, axis="y", color="#2d2d4e", linewidth=0.8, linestyle="--", zorder=0)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


@router.message(F.text == "📋 Сводка на сегодня")
async def today_summary(message: Message):
    user = await get_user(message.from_user.id)
    today = user_today(user.get("utc_offset", 0))

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
        f"📋 <b>Сводка на сегодня</b> — {today}\n\n{nutrition_block}\n\n{workout_block}",
        reply_markup=main_menu(),
    )


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    user = await get_user(message.from_user.id)

    all_time, workouts, prs, nutrition = await asyncio.gather(
        get_all_time_stats(message.from_user.id),
        get_last_workouts_rich(message.from_user.id, 5),
        get_exercise_prs(message.from_user.id, 6),
        get_nutrition_week_avg(message.from_user.id),
    )

    lines = ["📊 <b>Статистика</b>\n"]

    # Общий итог
    if all_time["total_workouts"] > 0:
        lines.append(
            f"🏋️ Тренировок: <b>{all_time['total_workouts']}</b>  ·  "
            f"Общий тоннаж: <b>{all_time['total_tonnage']:,.0f} кг</b>\n"
        )

    # Последние тренировки (только с реальными подходами)
    if workouts:
        lines.append("<b>Последние тренировки:</b>")
        for w in workouts:
            day_label = DAY_TYPES.get(w["day_type"], w["day_type"].replace("_", " ").title())
            week_label = WEEK_TYPES.get(w["week_type"], w["week_type"])
            d = w["date"][5:].replace("-", ".")
            sets_str = f"{w['set_count']} подх." if w.get("set_count") else ""
            lines.append(
                f"📅 {d} · <b>{day_label}</b> ({week_label})\n"
                f"   🏋️ {w['total_tonnage']:.0f} кг · RPE {w['avg_rpe']:.1f}"
                + (f" · {sets_str}" if sets_str else "")
            )

        # Тренд тоннажа
        if len(workouts) >= 2:
            first = workouts[-1]["total_tonnage"]
            last = workouts[0]["total_tonnage"]
            diff = last - first
            pct = (diff / first * 100) if first > 0 else 0
            sign = "+" if diff >= 0 else ""
            arrow = "📈" if diff >= 0 else "📉"
            lines.append(f"\n{arrow} Тоннаж: {sign}{diff:.0f} кг ({sign}{pct:.0f}%) за {len(workouts)} трен.")
    else:
        lines.append("Тренировок пока нет.")

    # Личные рекорды
    if prs:
        lines.append("\n🏆 <b>Личные рекорды:</b>")
        for pr in prs:
            lines.append(f"• {pr['exercise']}: <b>{pr['max_weight']:.0f} кг</b> × {pr['reps']} повт.")

    # Среднее питание за 7 дней
    if nutrition["days_tracked"] > 0:
        cal_pct = int(nutrition["avg_calories"] / user["goal_calories"] * 100) if user["goal_calories"] else 0
        prot_pct = int(nutrition["avg_protein"] / user["goal_protein"] * 100) if user["goal_protein"] else 0
        lines.append(
            f"\n🍽 <b>Питание (ср. за {nutrition['days_tracked']} дн. из 7):</b>\n"
            f"🔥 {nutrition['avg_calories']:.0f} / {user['goal_calories']} ккал ({cal_pct}%)\n"
            f"🥩 Белок: {nutrition['avg_protein']:.0f} / {user['goal_protein']}г ({prot_pct}%)"
        )

    await send_nav(message, "\n".join(lines), reply_markup=main_menu())
    sent = await message.answer(
        "📊 Дополнительный анализ:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Графики прогресса", callback_data="show_charts")],
            [InlineKeyboardButton(text="📊 Тоннаж по неделям", callback_data="show_tonnage")],
            [
                InlineKeyboardButton(text="💪 1RM", callback_data="show_1rm"),
                InlineKeyboardButton(text="⚖️ Мышечный баланс", callback_data="show_muscle_balance"),
            ],
        ])
    )
    track_msg(message.from_user.id, sent.message_id)


def _build_charts(exercise_data: dict) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import datetime

    n = len(exercise_data)
    cols = 2
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(12, rows * 3.8))
    fig.patch.set_facecolor("#0d1117")
    if n == 1:
        axes = [[axes]]
    elif rows == 1:
        axes = [axes]

    flat_axes = [ax for row in axes for ax in (row if hasattr(row, '__iter__') else [row])]

    colors = ["#58a6ff", "#3fb950", "#f78166", "#d2a8ff", "#ffa657", "#79c0ff"]

    for idx, (exercise, history) in enumerate(exercise_data.items()):
        ax = flat_axes[idx]
        ax.set_facecolor("#161b22")
        for spine in ax.spines.values():
            spine.set_color("#30363d")

        dates = [datetime.strptime(h["date"], "%Y-%m-%d") for h in history]
        weights = [h["max_weight"] for h in history]
        color = colors[idx % len(colors)]

        ax.plot(dates, weights, color=color, linewidth=2, zorder=3)
        ax.scatter(dates, weights, color=color, s=50, zorder=4)
        ax.fill_between(dates, weights, min(weights) * 0.97, alpha=0.15, color=color)

        # Подписи крайних значений
        ax.annotate(f"{weights[0]:.0f}", (dates[0], weights[0]),
                    textcoords="offset points", xytext=(-4, 6),
                    fontsize=8, color="#8b949e")
        ax.annotate(f"{weights[-1]:.0f}", (dates[-1], weights[-1]),
                    textcoords="offset points", xytext=(-4, 6),
                    fontsize=9, color=color, fontweight="bold")

        ax.set_title(exercise, color="#e6edf3", fontsize=10, fontweight="bold", pad=8)
        ax.tick_params(colors="#8b949e", labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax