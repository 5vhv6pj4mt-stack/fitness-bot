import hmac
import hashlib
import json
import logging
import time
from datetime import date
from urllib.parse import unquote, parse_qsl

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import BOT_TOKEN, DB_PATH

logging.basicConfig(level=logging.INFO)
from database.db import (
    init_db,
    get_user, update_user, get_day_nutrition, get_day_food_entries,
    get_last_workouts, get_workout_sets, log_food,
    get_user_program, get_user_day_types, get_user_week_types,
    get_active_workout, get_workout_by_id, create_workout, save_set, finish_workout,
    update_workout_progress, discard_all_active_workouts,
    get_food_entry, update_food_entry, delete_food_entry,
    get_tonnage_by_weeks, get_exercise_prs, get_all_time_stats,
    get_nutrition_week_avg, get_daily_nutrition_7d, get_avg_rpe_recent,
    get_exercise_weight_history, get_user_exercises,
    save_workout_analysis, get_workout_analysis,
    get_last_workout_by_day,
    get_frequent_foods,
)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://web.telegram.org",
        "https://webk.telegram.org",
        "https://webz.telegram.org",
        "https://oracle-bot-bot.duckdns.org",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["x-init-data", "content-type"],
)

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


def today() -> str:
    return date.today().isoformat()


@app.get("/api/health")
async def health():
    try:
        import aiosqlite as _aio
        async with _aio.connect(DB_PATH) as db:
            await db.execute("SELECT 1")
    except Exception as e:
        raise HTTPException(status_code=503, detail="DB unavailable")
    return {"status": "ok"}


def validate_init_data(init_data: str) -> int:
    """Проверяет Telegram initData и возвращает user_id."""
    if not init_data:
        raise HTTPException(status_code=401, detail="Empty initData")

    params = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", "")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData")

    auth_date = int(params.get("auth_date", 0))
    if abs(int(time.time()) - auth_date) > 3600:
        raise HTTPException(status_code=401, detail="initData expired")

    user_data = json.loads(params.get("user", "{}"))
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No user in initData")
    return user_id


async def get_current_day(user: dict):
    week_type = user["current_week_type"]
    day_index = user["current_day_index"]
    day_types = await get_user_day_types(user["user_id"], week_type)
    if not day_types:
        return "", week_type, []
    day_type = day_types[day_index % len(day_types)]
    exercises = await get_user_program(user["user_id"], week_type, day_type)
    return day_type, week_type, exercises


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from datetime import date as date_cls, timedelta
    nutrition = await get_day_nutrition(user_id, today())
    workouts = await get_last_workouts(user_id, 8)
    day_type, week_type, exercises = await get_current_day(user)

    workout_history = [
        {
            "date": w["date"],
            "day_label": DAY_TYPES.get(w["day_type"], w["day_type"]),
            "week_label": WEEK_TYPES.get(w["week_type"], w["week_type"]),
            "tonnage": round(w["total_tonnage"] or 0),
            "avg_rpe": round(w["avg_rpe"] or 0, 1),
        }
        for w in workouts
    ]

    # Week stats: current week vs previous week
    today_date = date_cls.today()
    week_start = today_date - timedelta(days=today_date.weekday())
    prev_week_start = week_start - timedelta(weeks=1)
    this_week = [w for w in workouts if w["date"] >= str(week_start)]
    prev_week = [w for w in workouts if str(prev_week_start) <= w["date"] < str(week_start)]
    this_tonnage = sum(w["total_tonnage"] or 0 for w in this_week)
    prev_tonnage = sum(w["total_tonnage"] or 0 for w in prev_week)
    delta = round(this_tonnage - prev_tonnage)

    return {
        "user": {
            "name": user["name"],
            "weight": user["weight"],
            "week": user["current_week"],
        },
        "next_workout": {
            "day_type": day_type,
            "day_label": DAY_TYPES.get(day_type, day_type),
            "week_label": WEEK_TYPES.get(week_type, week_type),
            "exercises": [
                {"name": ex["exercise"], "sets": ex["sets"], "reps": ex["reps_range"], "weight": ex["weight"]}
                for ex in exercises[:4]
            ],
            "total_exercises": len(exercises),
        },
        "nutrition_today": nutrition,
        "nutrition_goals": {
            "calories": user["goal_calories"],
            "protein": user["goal_protein"],
            "carbs": user["goal_carbs"],
            "fat": user["goal_fat"],
        },
        "workout_history": workout_history,
        "week_stats": {
            "workouts_count": len(this_week),
            "tonnage": round(this_tonnage),
            "delta": delta,
        },
    }


# ── Workout ───────────────────────────────────────────────────────────────────

@app.get("/api/workout/plan")
async def workout_plan(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    day_type, week_type, exercises = await get_current_day(user)
    active = await get_active_workout(user_id)

    return {
        "day_type": day_type,
        "day_label": DAY_TYPES.get(day_type, day_type),
        "week_type": week_type,
        "week_label": WEEK_TYPES.get(week_type, week_type),
        "week_num": user["current_week"],
        "exercises": exercises,
        "active_workout": dict(active) if active else None,
    }


class StartWorkoutRequest(BaseModel):
    pass


@app.post("/api/workout/start")
async def start_workout(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await discard_all_active_workouts(user_id)
    day_type, week_type, exercises = await get_current_day(user)
    if not exercises:
        raise HTTPException(status_code=400, detail="No program found")

    workout_id = await create_workout(user_id, today(), day_type, user["current_week"], week_type)
    return {"workout_id": workout_id, "day_type": day_type, "exercises": exercises}


class LogSetRequest(BaseModel):
    workout_id: int = Field(gt=0)
    exercise: str = Field(min_length=1, max_length=100)
    set_number: int = Field(ge=1)
    planned_weight: float = Field(ge=0)
    actual_weight: float = Field(ge=0, le=1000)
    reps: int = Field(ge=1, le=100)
    rpe: float = Field(ge=0, le=10)
    notes: str | None = Field(None, max_length=500)


@app.post("/api/workout/log-set")
async def log_set_endpoint(body: LogSetRequest, x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    workout = await get_workout_by_id(body.workout_id)
    if not workout or workout["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await save_set(
        body.workout_id, body.exercise, body.set_number,
        body.planned_weight, body.actual_weight, body.reps, body.rpe, body.notes
    )
    await update_workout_progress(body.workout_id, 0, 0)
    return {"ok": True}


class SetData(BaseModel):
    actual_weight: float = Field(ge=0, le=1000)
    reps: int = Field(ge=1, le=100)
    rpe: float = Field(ge=0, le=10)
    exercise: str = Field(default="", max_length=100)


class FinishWorkoutRequest(BaseModel):
    workout_id: int = Field(gt=0)
    sets: list[SetData] = Field(min_length=0, max_length=200)
    day_type: str = Field(max_length=50)
    week_type: str = Field(max_length=50)


async def _run_workout_analysis(workout_id: int, user: dict, day_type: str,
                                week_type: str, sets: list[dict]):
    try:
        from services.ai_service import analyze_workout
        prev = await get_last_workout_by_day(user["user_id"], day_type)
        prev_text = ""
        if prev:
            prev_sets = await get_workout_sets(prev["id"])
            prev_text = "\n".join(
                f"  {s['exercise']}: {s['actual_weight']}кг × {s['reps']} повт., RPE {s['rpe']}"
                for s in prev_sets
            )
        analysis = await analyze_workout(
            day_type, week_type, sets, prev_text, user.get("weight", 70)
        )
        await save_workout_analysis(workout_id, analysis)
    except Exception as e:
        logging.error(f"AI workout analysis failed: {e}")


@app.post("/api/workout/finish")
async def finish_workout_endpoint(
    body: FinishWorkoutRequest,
    background_tasks: BackgroundTasks,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    workout = await get_workout_by_id(body.workout_id)
    if not workout or workout["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tonnage = sum(s.actual_weight * s.reps for s in body.sets)
    avg_rpe = sum(s.rpe for s in body.sets) / len(body.sets) if body.sets else 0

    from datetime import datetime as dt
    try:
        created_dt = dt.fromisoformat(workout["created_at"])
        duration_minutes = int((dt.utcnow() - created_dt).total_seconds() / 60)
    except Exception:
        duration_minutes = 0

    await finish_workout(body.workout_id, tonnage, avg_rpe)

    # Продвигаем программу
    day_types = await get_user_day_types(user_id, user["current_week_type"])
    week_types = await get_user_week_types(user_id)
    next_day_index = user["current_day_index"] + 1
    next_week_type = user["current_week_type"]
    next_week_num = user["current_week"]

    if next_day_index >= len(day_types):
        next_day_index = 0
        if week_types and user["current_week_type"] in week_types:
            idx = week_types.index(user["current_week_type"])
            next_week_type = week_types[(idx + 1) % len(week_types)]
        next_week_num += 1

    await update_user(user_id,
                      current_day_index=next_day_index,
                      current_week_type=next_week_type,
                      current_week=next_week_num)

    sets_for_analysis = [
        {"exercise": s.exercise, "actual_weight": s.actual_weight, "reps": s.reps, "rpe": s.rpe}
        for s in body.sets
    ]
    background_tasks.add_task(
        _run_workout_analysis,
        body.workout_id, user, body.day_type, body.week_type, sets_for_analysis
    )

    return {
        "workout_id": body.workout_id,
        "tonnage": round(tonnage),
        "avg_rpe": round(avg_rpe, 1),
        "sets_count": len(body.sets),
        "duration_minutes": duration_minutes,
    }


@app.get("/api/workout/{workout_id}/analysis")
async def workout_analysis_endpoint(
    workout_id: int,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    workout = await get_workout_by_id(workout_id)
    if not workout or workout["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    analysis = await get_workout_analysis(workout_id)
    return {"ready": analysis is not None, "analysis": analysis}


# ── Nutrition ─────────────────────────────────────────────────────────────────

_MEAL_ORDER = ['breakfast', 'lunch', 'snack', 'dinner', 'other']
_MEAL_META = {
    'breakfast': {'icon': '🌅', 'label': 'Завтрак'},
    'lunch':     {'icon': '☀️',  'label': 'Обед'},
    'snack':     {'icon': '🌆', 'label': 'Перекус'},
    'dinner':    {'icon': '🌙', 'label': 'Ужин'},
    'other':     {'icon': '📦', 'label': 'Другое'},
}

def _detect_meal_type() -> str:
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 10:   return 'breakfast'
    if hour < 14:   return 'lunch'
    if hour < 18:   return 'snack'
    return 'dinner'


@app.get("/api/nutrition")
async def nutrition_today(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    raw_entries = await get_day_food_entries(user_id, today())
    totals = await get_day_nutrition(user_id, today())

    groups: dict[str, list] = {}
    for e in raw_entries:
        mt = e.get("meal_type") or "other"
        groups.setdefault(mt, []).append({
            "id": e["id"],
            "time": e["created_at"][11:16],
            "description": e["description"],
            "calories": round(e["calories"]),
            "protein": round(e["protein"], 1),
            "carbs": round(e["carbs"], 1),
            "fat": round(e["fat"], 1),
            "meal_type": mt,
        })

    meal_groups = []
    for mt in _MEAL_ORDER:
        if mt in groups:
            meta = _MEAL_META[mt]
            grp_entries = groups[mt]
            meal_groups.append({
                "meal_type": mt,
                "icon": meta["icon"],
                "label": meta["label"],
                "calories": sum(e["calories"] for e in grp_entries),
                "entries": grp_entries,
            })

    return {
        "entries": [e for g in meal_groups for e in g["entries"]],
        "meal_groups": meal_groups,
        "totals": {k: round(v, 1) for k, v in totals.items()},
        "goals": {
            "calories": user["goal_calories"],
            "protein": user["goal_protein"],
            "carbs": user["goal_carbs"],
            "fat": user["goal_fat"],
        },
    }


class LogFoodRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@app.post("/api/nutrition/log")
async def log_food_endpoint(body: LogFoodRequest, x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    from services.ai_service import parse_food
    result = await parse_food(body.text)
    meal_type = _detect_meal_type()
    entry_id = await log_food(
        user_id, today(),
        result.get("description", body.text[:100]),
        result["calories"], result["protein"], result["carbs"], result["fat"],
        meal_type=meal_type,
    )
    return {
        "id": entry_id,
        "meal_type": meal_type,
        "description": result.get("description", body.text[:100]),
        "calories": round(result["calories"]),
        "protein": round(result["protein"], 1),
        "carbs": round(result["carbs"], 1),
        "fat": round(result["fat"], 1),
    }


class UpdateFoodRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@app.patch("/api/nutrition/{entry_id}")
async def update_food_endpoint(
    entry_id: int,
    body: UpdateFoodRequest,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    entry = await get_food_entry(entry_id)
    if not entry or entry["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    from services.ai_service import parse_food
    result = await parse_food(body.text)
    desc = result.get("description", body.text[:300])
    await update_food_entry(
        entry_id, desc,
        result["calories"], result["protein"], result["carbs"], result["fat"],
    )
    return {
        "id": entry_id,
        "description": desc,
        "calories": round(result["calories"]),
        "protein": round(result["protein"], 1),
        "carbs": round(result["carbs"], 1),
        "fat": round(result["fat"], 1),
    }


@app.delete("/api/nutrition/{entry_id}")
async def delete_food_endpoint(
    entry_id: int,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    entry = await get_food_entry(entry_id)
    if not entry or entry["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    await delete_food_entry(entry_id)
    return {"ok": True}


@app.get("/api/program")
async def program_endpoint(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    week_type = user["current_week_type"]
    current_day_index = user["current_day_index"]
    current_week = user["current_week"]

    day_types = await get_user_day_types(user_id, week_type)
    all_week_types = await get_user_week_types(user_id)
    total_weeks = len(all_week_types) if all_week_types else 3
    week_in_cycle = ((current_week - 1) % total_weeks) + 1

    recent_workouts = await get_last_workouts(user_id, limit=30)

    days = []
    for i, day_type in enumerate(day_types):
        exercises = await get_user_program(user_id, week_type, day_type)
        if i < current_day_index:
            status = "done"
            matching = [w for w in recent_workouts
                        if w["day_type"] == day_type and w["week_type"] == week_type]
            w = matching[0] if matching else None
            workout_info = {"date": w["date"], "tonnage": round(w["total_tonnage"] or 0)} if w else None
        elif i == current_day_index:
            status = "current"
            workout_info = None
        else:
            status = "upcoming"
            workout_info = None

        days.append({
            "index": i,
            "day_type": day_type,
            "day_label": DAY_TYPES.get(day_type, day_type),
            "status": status,
            "workout": workout_info,
            "exercises": [
                {
                    "name": ex["exercise"],
                    "sets": ex["sets"],
                    "reps": ex["reps_range"],
                    "weight": ex["weight"],
                }
                for ex in exercises
            ],
        })

    # Next week preview: first day of next week type
    week_order = list(all_week_types) if all_week_types else ["strength", "volume", "deload"]
    cur_idx = week_order.index(week_type) if week_type in week_order else 0
    next_week_type = week_order[(cur_idx + 1) % len(week_order)]
    next_day_types = await get_user_day_types(user_id, next_week_type)
    next_day_type = next_day_types[0] if next_day_types else None
    next_exercises = await get_user_program(user_id, next_week_type, next_day_type) if next_day_type else []

    return {
        "week_type": week_type,
        "week_type_label": WEEK_TYPES.get(week_type, week_type),
        "week_number": current_week,
        "week_in_cycle": week_in_cycle,
        "total_weeks_in_cycle": total_weeks,
        "completed_days": current_day_index,
        "total_days": len(day_types),
        "days": days,
        "next_week": {
            "week_type": next_week_type,
            "week_type_label": WEEK_TYPES.get(next_week_type, next_week_type),
            "day_label": DAY_TYPES.get(next_day_type, next_day_type) if next_day_type else "",
            "exercises": [
                {"name": ex["exercise"], "sets": ex["sets"], "reps": ex["reps_range"], "weight": ex["weight"]}
                for ex in next_exercises
            ],
        } if next_day_type else None,
    }


@app.get("/api/nutrition/templates")
async def nutrition_templates(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    foods = await get_frequent_foods(user_id, limit=10)
    return {"templates": foods}


@app.post("/api/nutrition/log-template")
async def log_template(body: LogFoodRequest, x_init_data: str = Header(alias="x-init-data")):
    """Log a food using a pre-parsed template (skip AI parsing, use stored КБЖУ)."""
    user_id = validate_init_data(x_init_data)
    from services.ai_service import parse_food
    result = await parse_food(body.text)
    meal_type = _detect_meal_type()
    entry_id = await log_food(
        user_id, today(),
        result.get("description", body.text[:100]),
        result["calories"], result["protein"], result["carbs"], result["fat"],
        meal_type=meal_type,
    )
    return {
        "id": entry_id,
        "meal_type": meal_type,
        "description": result.get("description", body.text[:100]),
        "calories": round(result["calories"]),
        "protein": round(result["protein"], 1),
        "carbs": round(result["carbs"], 1),
        "fat": round(result["fat"], 1),
    }


@app.get("/api/progress")
async def progress_endpoint(x_init_data: str = Header(alias="x-init-data")):
    from datetime import date as date_cls, timedelta
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today_date = date_cls.today()
    DAY_NAMES_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    tonnage_raw = await get_tonnage_by_weeks(user_id, n_weeks=8)
    tonnage_map = {item["week_label"]: item["tonnage"] for item in tonnage_raw}
    tonnage_weeks = []
    for i in range(7, -1, -1):
        week_date = today_date - timedelta(weeks=i)
        iso_week = week_date.strftime('%Y-W%W')
        tonnage_weeks.append({
            "label": "Сейчас" if i == 0 else f"Н-{i}",
            "tonnage": round(tonnage_map.get(iso_week, 0)),
        })

    all_time = await get_all_time_stats(user_id)
    avg_rpe = await get_avg_rpe_recent(user_id)
    prs = await get_exercise_prs(user_id, limit=6)
    nutr_avg = await get_nutrition_week_avg(user_id)

    daily_raw = await get_daily_nutrition_7d(user_id)
    nutrition_daily = []
    for i in range(6, -1, -1):
        d = today_date - timedelta(days=i)
        day_str = d.strftime('%Y-%m-%d')
        nutrition_daily.append({
            "day_label": DAY_NAMES_RU[d.weekday()],
            "calories": round(daily_raw.get(day_str, 0)),
            "is_today": i == 0,
        })

    exercises = await get_user_exercises(user_id)

    return {
        "tonnage_weeks": tonnage_weeks,
        "stats": {
            "total_workouts": all_time["total_workouts"],
            "avg_rpe": avg_rpe,
            "body_weight": user.get("weight"),
        },
        "exercise_prs": [
            {"exercise": p["exercise"], "weight": p["max_weight"], "reps": p["reps"]}
            for p in prs
        ],
        "nutrition_week": {
            "avg_calories": round(nutr_avg["avg_calories"]),
            "avg_protein": round(nutr_avg["avg_protein"]),
            "avg_carbs": round(nutr_avg["avg_carbs"]),
            "avg_fat": round(nutr_avg["avg_fat"]),
            "days_tracked": nutr_avg["days_tracked"],
        },
        "nutrition_daily": nutrition_daily,
        "goals": {
            "calories": user.get("goal_calories") or 2500,
            "protein": user.get("goal_protein") or 150,
            "carbs": user.get("goal_carbs") or 250,
            "fat": user.get("goal_fat") or 80,
        },
        "exercises": exercises,
    }


@app.get("/api/progress/exercise")
async def exercise_history_endpoint(
    name: str,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    history = await get_exercise_weight_history(user_id, name, limit=8)
    return {"history": history}
