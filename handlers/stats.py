import asyncio
import io
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from database.db import (get_user, get_last_workouts, get_workout_sets, get_day_nutrition,
                         get_user_day_types, get_last_workouts_rich, get_all_time_stats,
                         get_exercise_prs, get_nutrition_week_avg,
                         get_top_exercises, get_exercise_history,
                         get_best_sets_for_1rm, get_muscle_volume)
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
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
        ax.yaxis.set_label_text("кг", color="#8b949e", fontsize=8)
        ax.grid(True, color="#21262d", linewidth=0.8, zorder=0)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")

    # Скрываем лишние оси
    for idx in range(n, len(flat_axes)):
        flat_axes[idx].set_visible(False)

    fig.suptitle("Прогресс весов", color="#e6edf3", fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


@router.callback_query(F.data == "show_charts")
async def show_charts(callback: CallbackQuery):
    await callback.answer("⏳ Строю графики...")
    status = await callback.message.answer("⏳ Генерирую графики прогресса...")

    top = await get_top_exercises(callback.from_user.id, 6)
    if not top:
        await status.edit_text("📭 Недостаточно данных. Нужно минимум 2 тренировки на упражнение.")
        return

    exercise_data = {}
    for ex in top:
        history = await get_exercise_history(callback.from_user.id, ex, 15)
        if len(history) >= 2:
            exercise_data[ex] = history

    if not exercise_data:
        await status.edit_text("📭 Недостаточно данных для графиков.")
        return

    loop = asyncio.get_event_loop()
    img_bytes = await loop.run_in_executor(None, _build_charts, exercise_data)

    await status.delete()
    await callback.message.answer_photo(
        BufferedInputFile(img_bytes, filename="progress.png"),
        caption=f"📈 <b>Прогресс весов</b> — топ {len(exercise_data)} упражнений",
        parse_mode="HTML",
    )


# ── 1RM Калькулятор ────────────────────────────────────────────────────────────

# Упражнения где к доп. весу прибавляем вес тела
_BODYWEIGHT_EXERCISES = {
    "подтягивания обратным хватом",
    "подтягивания обратным хватом с весом",
    "подтягивания широкие",
    "подтягивания широкие с весом",
    "подтяг-я обр. хватом",
    "подтягивания обр. хватом",
    "отжимания на брусьях",
    "отжимания",
}


def _calc_1rm(sets: list[dict], body_weight: float) -> list[dict]:
    best = {}
    for s in sets:
        ex = s["exercise"]
        is_bw = ex.lower() in _BODYWEIGHT_EXERCISES
        if not is_bw and s["weight"] <= 0:
            continue  # пропускаем нулевой вес для не-бодивейт упражнений
        effective = (body_weight + s["weight"]) if is_bw else s["weight"]
        e1rm = effective * (1 + s["reps"] / 30)
        if ex not in best or e1rm > best[ex]["e1rm"]:
            best[ex] = {
                "exercise": ex,
                "weight": s["weight"],
                "effective": effective,
                "reps": s["reps"],
                "e1rm": e1rm,
                "is_bw": is_bw,
            }
    return sorted(best.values(), key=lambda x: -x["e1rm"])


@router.callback_query(F.data == "show_1rm")
async def show_1rm(callback: CallbackQuery):
    await callback.answer()
    user = await get_user(callback.from_user.id)
    body_weight = user.get("weight", 0)
    raw_sets = await get_best_sets_for_1rm(callback.from_user.id)
    if not raw_sets:
        await callback.message.answer("📭 Нет данных. Нужны подходы с 1–12 повторениями.")
        return

    results = _calc_1rm(raw_sets, body_weight)
    if not results:
        await callback.message.answer("📭 Недостаточно данных для расчёта.")
        return

    lines = [f"💪 <b>Расчётный 1RM</b> (формула Epley, вес тела {body_weight:.0f}кг)\n"]
    max_1rm = results[0]["e1rm"]
    for s in results[:12]:
        bar = "█" * max(1, int(s["e1rm"] / max_1rm * 10))
        if s["is_bw"]:
            weight_str = f"тело {body_weight:.0f}" + (f"+{s['weight']:.0f}" if s["weight"] > 0 else "") + f"кг × {s['reps']}"
        else:
            weight_str = f"{s['weight']:.0f}кг × {s['reps']}"
        lines.append(
            f"<b>{s['exercise']}</b>\n"
            f"  {weight_str} → <b>{s['e1rm']:.0f} кг</b>  <code>{bar}</code>"
        )

    lines.append("\n<i>1RM = вес × (1 + повторы / 30)</i>")
    await callback.message.answer("\n".join(lines), parse_mode="HTML")


# ── Мышечный баланс ────────────────────────────────────────────────────────────

_MUSCLE_MAP = {
    # Горизонтальный жим (грудь + передние дельты)
    "горизонтальный жим": [
        "жим штанги наклонной", "жим гантелей лежа", "жим гантелей лёжа",
        "жим штанги лёжа", "жим штанги лежа",
    ],
    # Горизонтальная тяга (широчайшие + ромбовидные)
    "горизонтальная тяга": [
        "тяга штанги в наклоне", "тяга горизонтального блока",
        "тяга гантели в наклоне",
    ],
    # Вертикальная тяга (широчайшие)
    "вертикальная тяга": [
        "подтягивания обратным хватом", "подтягивания широкие",
        "подтягивания широкие с весом", "подтягивания обратным хватом с весом",
        "подтяг-я обр. хватом", "тяга вертикального блока широким хватом",
    ],
    # Вертикальный жим (дельты)
    "вертикальный жим": [
        "армейский жим сидя", "жим гантелей сидя", "армейский жим",
    ],
    # Задние дельты / ротаторы
    "задние дельты": [
        "тяга лица", "обратная бабочка", "махи в наклоне",
    ],
    # Квадрицепс
    "квадрицепс": [
        "жим ногами", "болгарские выпады", "приседания со штангой", "приседания",
    ],
    # Бицепс бедра
    "бицепс бедра": [
        "румынская тяга", "сгибания ног", "становая тяга",
    ],
    # Икры
    "икры": ["подъем на носки", "подъём на носки"],
    # Бицепс
    "бицепс": [
        "суперсет: бицепс", "бицепс (штанга) суперсет",
        "суперсет: бицепс+трицепс",
    ],
    # Трицепс
    "трицепс": [
        "суперсет: трицепс", "трицепс суперсет",
        "суперсет: бицепс+трицепс",
    ],
}

_BALANCE_PAIRS = [
    ("горизонтальный жим", "горизонтальная тяга",
     "Push/Pull (гориз.)", 0.8, 1.2,
     "тяговые упражнения отстают — добавь тягу в наклоне",
     "жим преобладает над тягой — следи за осанкой"),
    ("вертикальный жим", "вертикальная тяга",
     "Push/Pull (верт.)", 0.5, 0.9,
     "подтягивания отстают — добавь тягу сверху",
     "вертикальная тяга сильно превышает жим — проверь дельты"),
    ("квадрицепс", "бицепс бедра",
     "Квад/Бицепс бедра", 1.0, 1.5,
     "задняя поверхность отстаёт — добавь румынку или сгибания",
     "передняя/задняя поверхность в норме"),
    ("горизонтальный жим", "задние дельты",
     "Передние/задние дельты", 2.0, 4.0,
     "задние дельты сильно отстают — добавь тягу лица и обратную бабочку",
     "передние дельты перегружены относительно задних"),
]


def _classify_volume(exercise_volumes: list[dict]) -> dict:
    totals = {g: 0.0 for g in _MUSCLE_MAP}
    for item in exercise_volumes:
        name = item["exercise"].lower()
        for group, exercises in _MUSCLE_MAP.items():
            if any(ex in name or name in ex for ex in exercises):
                totals[group] += item["volume"]
                break
    return {g: v for g, v in totals.items() if v > 0}


def _muscle_balance_period_kb(active_days: int = None) -> InlineKeyboardMarkup:
    options = [(28, "4 нед"), (42, "6 нед"), (56, "8 нед"), (84, "12 нед")]
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"{'✅ ' if days == active_days else ''}{label}",
            callback_data=f"mb:{days}"
        ) for days, label in options
    ]])


async def _render_muscle_balance(user_id: int, days: int) -> str:
    raw = await get_muscle_volume(user_id, days=days)
    if not raw:
        return "📭 Недостаточно данных за этот период."
    volumes = _classify_volume(raw)
    if not volumes:
        return "📭 Не удалось определить мышечные группы."

    weeks = days // 7
    lines = [f"⚖️ <b>Мышечный баланс</b> — последние {weeks} нед.\n"]
    max_vol = max(volumes.values())
    for group, vol in sorted(volumes.items(), key=lambda x: -x[1]):
        bar_len = int(vol / max_vol * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"<code>{bar}</code> <b>{group.capitalize()}</b>: {vol/1000:.1f}т")

    warnings = []
    for g1, g2, label, low, high, warn_low, warn_high in _BALANCE_PAIRS:
        v1 = volumes.get(g1, 0)
        v2 = volumes.get(g2, 0)
        if v1 == 0 or v2 == 0:
            continue
        ratio = v1 / v2
        if ratio < low:
            warnings.append(f"⚠️ <b>{label}</b> ({ratio:.1f}): {warn_low}")
        elif ratio > high:
            warnings.append(f"⚠️ <b>{label}</b> ({ratio:.1f}): {warn_high}")
        else:
            warnings.append(f"✅ <b>{label}</b> ({ratio:.1f}): баланс в норме")
    if warnings:
        lines.append("\n<b>Анализ:</b>")
        lines.extend(warnings)
    return "\n".join(lines)


@router.callback_query(F.data == "show_muscle_balance")
async def show_muscle_balance(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "⚖️ <b>Мышечный баланс</b> — выбери период:",
        reply_markup=_muscle_balance_period_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mb:"))
async def cb_muscle_balance(callback: CallbackQuery):
    days = int(callback.data.split(":")[1])
    await callback.answer()
    text = await _render_muscle_balance(callback.from_user.id, days)
    await callback.message.edit_text(
        text,
        reply_markup=_muscle_balance_period_kb(active_days=days),
        parse_mode="HTML",
    )
