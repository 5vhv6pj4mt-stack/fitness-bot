import hmac
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import unquote, parse_qsl

import aiosqlite

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import BOT_TOKEN, DB_PATH, TEMP_VIDEO_DIR, QUEUE_DIR

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
    get_nutrition_week_avg, get_daily_nutrition_7d, get_avg_rpe_recent, get_meal_suggestions,
    get_exercise_weight_history, get_user_exercises, get_last_exercise_set,
    save_workout_analysis, get_workout_analysis,
    get_last_workout_by_day,
    get_frequent_foods,
    get_water_today, add_water_glass,
    log_weight, get_weight_history,
    log_measurements, get_latest_measurements, get_measurements_month_ago,
    get_week_workouts, get_week_nutrition_avg,
    update_exercise_weight,
    delete_workout_set, update_workout_set, recalculate_workout_totals, get_recent_workouts,
    save_press_analysis,
)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await init_db()
    Path(TEMP_VIDEO_DIR).mkdir(parents=True, exist_ok=True)
    for _sub in ("pending", "processing", "done"):
        (Path(QUEUE_DIR) / _sub).mkdir(parents=True, exist_ok=True)
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

from constants import DAY_TYPES, WEEK_TYPES


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


def _cap_kbju(result: dict) -> dict:
    """Ограничивает значения КБЖУ разумными пределами на случай ошибки AI."""
    caps = {"calories": 3000, "protein": 300, "carbs": 300, "fat": 300}
    for k, cap in caps.items():
        if k in result:
            result[k] = max(0.0, min(float(result[k]), cap))
    return result


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
    if abs(int(time.time()) - auth_date) > 86400:  # 24ч — десктоп может держать сессию долго
        raise HTTPException(status_code=401, detail="initData expired")

    user_data = json.loads(params.get("user", "{}"))
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No user in initData")
    return user_id


def _suggested_weight(last_weight: float, last_rpe: float | None) -> float:
    rpe = last_rpe or 8.0
    if rpe <= 7.0:
        factor = 1.05
    elif rpe <= 8.0:
        factor = 1.025
    elif rpe <= 8.5:
        factor = 1.0
    else:
        factor = 0.975
    raw = last_weight * factor
    # Round to nearest 2.5
    return round(round(raw / 2.5) * 2.5, 1)


def _parse_rest_secs(rest: str | None) -> int:
    if not rest or rest == '—':
        return 0
    s = 0
    import re
    m = re.search(r'(\d+)м', rest)
    sec = re.search(r'(\d+)с', rest)
    if m:
        s += int(m.group(1)) * 60
    if sec:
        s += int(sec.group(1))
    return s or 120


async def enrich_exercises_with_history(user_id: int, exercises: list) -> list:
    result = []
    for ex in exercises:
        last = await get_last_exercise_set(user_id, ex["exercise"])
        ex_dict = dict(ex)
        ex_dict["rest_secs"] = _parse_rest_secs(ex.get("rest"))
        if last:
            ex_dict["last_weight"] = last["actual_weight"]
            ex_dict["last_reps"] = last["reps"]
            ex_dict["last_rpe"] = last["rpe"]
            ex_dict["suggested_weight"] = _suggested_weight(last["actual_weight"], last["rpe"])
        else:
            ex_dict["last_weight"] = None
            ex_dict["last_reps"] = None
            ex_dict["last_rpe"] = None
            ex_dict["suggested_weight"] = ex.get("weight") or None
        result.append(ex_dict)
    return result


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
    enriched = await enrich_exercises_with_history(user_id, exercises)

    active_data = None
    if active:
        active_data = dict(active)
        sets = await get_workout_sets(active["id"])
        active_data["logged_sets"] = [
            {
                "id": s["id"],
                "exercise": s["exercise"],
                "actual_weight": s["actual_weight"],
                "reps": s["reps"],
                "rpe": s["rpe"],
            }
            for s in sets
        ]

    return {
        "day_type": day_type,
        "day_label": DAY_TYPES.get(day_type, day_type),
        "week_type": week_type,
        "week_label": WEEK_TYPES.get(week_type, week_type),
        "week_num": user["current_week"],
        "exercises": enriched,
        "active_workout": active_data,
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

    enriched = await enrich_exercises_with_history(user_id, exercises)
    workout_id = await create_workout(user_id, today(), day_type, user["current_week"], week_type)
    return {"workout_id": workout_id, "day_type": day_type, "exercises": enriched}


class LogSetRequest(BaseModel):
    workout_id: int = Field(gt=0)
    exercise: str = Field(min_length=1, max_length=100)
    set_number: int = Field(ge=1)
    planned_weight: float = Field(ge=0)
    actual_weight: float = Field(ge=0, le=1000)
    reps: int = Field(ge=1, le=100)
    rpe: float = Field(ge=0, le=10)
    notes: str | None = Field(None, max_length=500)
    ex_index: int = Field(default=0, ge=0)
    set_index: int = Field(default=0, ge=0)


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
    await update_workout_progress(body.workout_id, body.ex_index, body.set_index)
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

class ExerciseWeightRequest(BaseModel):
    exercise: str
    week_type: str
    day_type: str
    weight: float = Field(gt=0, lt=1000)


@app.get("/api/workout/recent")
async def recent_workouts(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    workouts = await get_recent_workouts(user_id, limit=10)
    result = []
    for w in workouts:
        sets = await get_workout_sets(w["id"])
        result.append({
            "id": w["id"],
            "date": w["date"],
            "day_type": DAY_TYPES.get(w.get("day_type", ""), w.get("day_type", "—")),
            "week_type": WEEK_TYPES.get(w.get("week_type", ""), w.get("week_type", "")),
            "tonnage": round(w.get("total_tonnage") or 0),
            "avg_rpe": round(w.get("avg_rpe") or 0, 1),
            "sets": [
                {
                    "id": s["id"],
                    "exercise": s["exercise"],
                    "set_number": s["set_number"],
                    "actual_weight": s["actual_weight"],
                    "reps": s["reps"],
                    "rpe": s["rpe"],
                }
                for s in sets
            ],
        })
    return {"workouts": result}


class UpdateSetRequest(BaseModel):
    actual_weight: float
    reps: int
    rpe: float = 8.0
    notes: str | None = None


@app.patch("/api/workout/set/{set_id}")
async def patch_set(
    set_id: int,
    body: UpdateSetRequest,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT w.user_id, ws.workout_id FROM workout_sets ws JOIN workouts w ON w.id=ws.workout_id WHERE ws.id=?",
            (set_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    workout_id = row["workout_id"]
    await update_workout_set(set_id, body.actual_weight, body.reps, body.rpe, body.notes)
    await recalculate_workout_totals(workout_id)
    return {"ok": True, "workout_id": workout_id}


@app.delete("/api/workout/set/{set_id}")
async def delete_set(set_id: int, x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    # verify ownership
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT w.user_id, ws.workout_id FROM workout_sets ws JOIN workouts w ON w.id=ws.workout_id WHERE ws.id=?",
            (set_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    workout_id = row["workout_id"]
    await delete_workout_set(set_id)
    await recalculate_workout_totals(workout_id)
    return {"ok": True, "workout_id": workout_id}


@app.patch("/api/workout/exercise-weight")
async def update_exercise_weight_endpoint(
    body: ExerciseWeightRequest,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    await update_exercise_weight(user_id, body.week_type, body.day_type, body.exercise, body.weight)
    return {"ok": True, "weight": body.weight}


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


WATER_GOAL = 8


@app.get("/api/water/today")
async def water_today(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    notif_water = bool(user.get("notif_water", 1)) if user else True
    goal = (user.get("water_goal") or WATER_GOAL) if user else WATER_GOAL
    glasses = await get_water_today(user_id, today())
    return {"glasses": glasses, "goal": goal, "notif_water": notif_water}


@app.post("/api/water/add")
async def water_add(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    goal = (user.get("water_goal") or WATER_GOAL) if user else WATER_GOAL
    glasses = await add_water_glass(user_id, today())
    return {"glasses": glasses, "goal": goal}


@app.post("/api/nutrition/log-photo")
async def log_food_photo_upload(
    x_init_data: str = Header(alias="x-init-data"),
    file: UploadFile = File(...),
):
    user_id = validate_init_data(x_init_data)
    if not file:
        raise HTTPException(status_code=400, detail="No file")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    from services.ai_service import parse_food_photo
    result = _cap_kbju(await parse_food_photo(image_bytes))
    meal_type = _detect_meal_type()
    entry_id = await log_food(
        user_id, today(),
        result.get("description", "Блюдо с фото"),
        result["calories"], result["protein"], result["carbs"], result["fat"],
        meal_type=meal_type,
    )
    return {
        "id": entry_id,
        "meal_type": meal_type,
        "description": result.get("description", "Блюдо с фото"),
        "calories": round(result["calories"]),
        "protein": round(result["protein"], 1),
        "carbs": round(result["carbs"], 1),
        "fat": round(result["fat"], 1),
    }


@app.post("/api/nutrition/log-voice")
async def log_food_voice(
    x_init_data: str = Header(alias="x-init-data"),
    file: UploadFile = File(...),
):
    user_id = validate_init_data(x_init_data)
    if not file:
        raise HTTPException(status_code=400, detail="No file")
    audio_bytes = await file.read()
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 25MB)")
    from services.ai_service import transcribe_voice, parse_food
    text = await transcribe_voice(audio_bytes, filename=file.filename or "voice.webm")
    if not text.strip():
        raise HTTPException(status_code=422, detail="Не удалось распознать речь")
    result = _cap_kbju(await parse_food(text))
    meal_type = _detect_meal_type()
    entry_id = await log_food(
        user_id, today(),
        result.get("description", text[:200]),
        result["calories"], result["protein"], result["carbs"], result["fat"],
        meal_type=meal_type,
    )
    return {
        "id": entry_id,
        "meal_type": meal_type,
        "description": result.get("description", text[:200]),
        "calories": round(result["calories"]),
        "protein": round(result["protein"], 1),
        "carbs": round(result["carbs"], 1),
        "fat": round(result["fat"], 1),
        "transcription": text,
    }


@app.get("/api/nutrition")
async def nutrition_today(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    raw_entries = await get_day_food_entries(user_id, today())
    totals = await get_day_nutrition(user_id, today())

    from datetime import datetime as _dt, timedelta as _td
    utc_offset = user.get("utc_offset") or 0

    def _local_time(created_at: str) -> str:
        try:
            return (_dt.fromisoformat(created_at) + _td(hours=utc_offset)).strftime("%H:%M")
        except Exception:
            return created_at[11:16]

    groups: dict[str, list] = {}
    for e in raw_entries:
        mt = e.get("meal_type") or "other"
        groups.setdefault(mt, []).append({
            "id": e["id"],
            "time": _local_time(e["created_at"]),
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
    result = _cap_kbju(await parse_food(body.text))
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
    result = _cap_kbju(await parse_food(body.text))
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

    days_in_week = len(day_types)
    remaining_days_this_week = max(0, days_in_week - current_day_index)
    remaining_full_weeks = max(0, total_weeks - week_in_cycle)
    days_until_next_cycle = remaining_days_this_week + remaining_full_weeks * days_in_week

    return {
        "week_type": week_type,
        "week_type_label": WEEK_TYPES.get(week_type, week_type),
        "week_number": current_week,
        "week_in_cycle": week_in_cycle,
        "total_weeks_in_cycle": total_weeks,
        "completed_days": current_day_index,
        "total_days": days_in_week,
        "days_until_next_cycle": days_until_next_cycle,
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
    meal_type = _detect_meal_type()
    foods = await get_meal_suggestions(user_id, meal_type, limit=8)
    return {"templates": foods}


@app.post("/api/nutrition/log-template")
async def log_template(body: LogFoodRequest, x_init_data: str = Header(alias="x-init-data")):
    """Log a food using a pre-parsed template (skip AI parsing, use stored КБЖУ)."""
    user_id = validate_init_data(x_init_data)
    from services.ai_service import parse_food
    result = _cap_kbju(await parse_food(body.text))
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


@app.get("/api/progress/week")
async def week_report_endpoint(x_init_data: str = Header(alias="x-init-data")):
    from datetime import date as date_cls, timedelta
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today = date_cls.today()
    week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    week_end = today.strftime('%Y-%m-%d')
    prev_start = (today - timedelta(days=today.weekday() + 7)).strftime('%Y-%m-%d')
    prev_end = (today - timedelta(days=today.weekday() + 1)).strftime('%Y-%m-%d')

    workouts = await get_week_workouts(user_id, week_start, week_end)
    prev_workouts = await get_week_workouts(user_id, prev_start, prev_end)
    nutr = await get_week_nutrition_avg(user_id, week_start, week_end)

    tonnage_this = sum(w.get("total_tonnage") or 0 for w in workouts)
    tonnage_prev = sum(w.get("total_tonnage") or 0 for w in prev_workouts)
    tonnage_delta = round(tonnage_this - tonnage_prev) if tonnage_prev else None

    DAY_TYPE_LABELS = {
        "upper_strength": "Верх — Сила", "upper_volume": "Верх — Объём", "legs": "Ноги",
    }

    return {
        "workouts": [
            {
                "date": w["date"],
                "day_type": DAY_TYPE_LABELS.get(w.get("day_type", ""), w.get("day_type", "—")),
                "tonnage": round(w.get("total_tonnage") or 0),
                "rpe": round(w.get("avg_rpe"), 1) if w.get("avg_rpe") is not None else None,
            }
            for w in workouts
        ],
        "workouts_count": len(workouts),
        "tonnage_this_week": round(tonnage_this),
        "tonnage_prev_week": round(tonnage_prev),
        "tonnage_delta": tonnage_delta,
        "nutrition": {
            "avg_calories": round(nutr["avg_calories"]),
            "avg_protein": round(nutr["avg_protein"]),
            "avg_carbs": round(nutr["avg_carbs"]),
            "avg_fat": round(nutr["avg_fat"]),
            "days_tracked": nutr["days_tracked"],
        },
        "goals": {
            "calories": user.get("goal_calories") or 2500,
            "protein": user.get("goal_protein") or 150,
            "carbs": user.get("goal_carbs") or 250,
            "fat": user.get("goal_fat") or 80,
        },
        "week_start": week_start,
        "days_planned": user.get("days_per_week") or 3,
    }


@app.get("/api/progress/exercise")
async def exercise_history_endpoint(
    name: str,
    x_init_data: str = Header(alias="x-init-data"),
):
    user_id = validate_init_data(x_init_data)
    history = await get_exercise_weight_history(user_id, name, limit=24)
    return {"history": history}


_MUSCLE_KEYWORDS: list[tuple[list[str], list[str]]] = [
    # keywords (lowercase, partial)  →  muscle group ids
    (["жим лёжа", "жим лежа", "жим гантелей", "жим штанги наклон", "отжима"], ["chest", "triceps", "shoulders"]),
    (["армейский жим", "жим стоя", "жим сидя"], ["shoulders", "triceps"]),
    (["разводка", "бабочка", "махи в наклоне", "тяга лица", "обратная баб"], ["shoulders", "back"]),
    (["подтяг", "тяга вертикальн", "тяга горизонт", "тяга штанги в наклоне", "тяга штанги", "ряды с гантел"], ["back", "biceps"]),
    (["бицепс", "бицепсов", "сгиб руки", "суперсет: бицепс"], ["biceps"]),
    (["трицепс", "трицепсов", "суперсет: трицепс", "разгибание рук"], ["triceps"]),
    (["присед", "жим ног", "болгарск", "выпады", "разгибания ног"], ["quads", "glutes"]),
    (["румынская тяга", "сгибания ног", "становая"], ["hamstrings", "glutes"]),
    (["подъём на носки", "подъем на носки", "икры"], ["calves"]),
    (["пресс", "планка", "скручивания"], ["abs"]),
    (["вис на перекладине"], ["back", "biceps"]),
]

_MUSCLE_META = {
    "chest":      {"label": "Грудь",       "group": "upper"},
    "back":       {"label": "Спина",        "group": "upper"},
    "shoulders":  {"label": "Плечи",        "group": "upper"},
    "biceps":     {"label": "Бицепс",       "group": "upper"},
    "triceps":    {"label": "Трицепс",      "group": "upper"},
    "abs":        {"label": "Пресс",        "group": "upper"},
    "quads":      {"label": "Квадрицепсы",  "group": "lower"},
    "hamstrings": {"label": "Бицепс бедра", "group": "lower"},
    "glutes":     {"label": "Ягодицы",      "group": "lower"},
    "calves":     {"label": "Икры",         "group": "lower"},
}


def _exercise_to_muscles(exercise: str) -> list[str]:
    ex_low = exercise.lower()
    for keywords, muscles in _MUSCLE_KEYWORDS:
        if any(k in ex_low for k in keywords):
            return muscles
    return []


@app.get("/api/progress/muscles")
async def muscles_endpoint(x_init_data: str = Header(alias="x-init-data")):
    from datetime import date as date_cls, timedelta
    user_id = validate_init_data(x_init_data)

    cutoff = str(date_cls.today() - timedelta(days=28))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT s.exercise, s.actual_weight * s.reps AS vol, w.date
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND w.date >= ? AND s.actual_weight > 0""",
            (user_id, cutoff),
        ) as cur:
            rows = await cur.fetchall()

    tonnage: dict[str, float] = {m: 0.0 for m in _MUSCLE_META}
    last_date: dict[str, str] = {}

    for row in rows:
        muscles = _exercise_to_muscles(row["exercise"])
        for m in muscles:
            tonnage[m] = tonnage.get(m, 0) + (row["vol"] or 0)
            prev = last_date.get(m)
            if not prev or row["date"] > prev:
                last_date[m] = row["date"]

    max_t = max(tonnage.values()) if any(tonnage.values()) else 1
    today_str = str(date_cls.today())

    result = []
    for muscle_id, meta in _MUSCLE_META.items():
        t = round(tonnage.get(muscle_id, 0))
        ld = last_date.get(muscle_id)
        days_since = (date_cls.fromisoformat(today_str) - date_cls.fromisoformat(ld)).days if ld else None
        result.append({
            "id": muscle_id,
            "label": meta["label"],
            "group": meta["group"],
            "tonnage_28d": t,
            "intensity": round(t / max_t, 3),
            "last_trained": ld,
            "days_since": days_since,
        })

    return {"groups": result}


# ── Profile ───────────────────────────────────────────────────────────────────

_GOAL_LABELS = {
    "weight_loss": "Похудение",
    "muscle_gain": "Набор массы",
    "mass": "Набор массы",
    "maintenance": "Поддержание формы",
    "strength": "Сила",
    "endurance": "Выносливость",
}
_EQUIPMENT_LABELS = {
    "gym": "Зал",
    "home": "Дома",
    "minimal": "Минимум инвентаря",
    "barbell": "Штанга + гантели",
}


@app.get("/api/profile")
async def profile_get(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    stats = await get_all_time_stats(user_id)
    avg_rpe = await get_avg_rpe_recent(user_id, limit=10)
    nutr_avg = await get_nutrition_week_avg(user_id)
    utc_offset = user.get("utc_offset") or 0
    tz_str = f"UTC+{utc_offset}" if utc_offset >= 0 else f"UTC{utc_offset}"
    return {
        "name": user["name"],
        "weight": user["weight"],
        "height": user["height"],
        "age": user["age"],
        "goal": user["goal"],
        "goal_label": _GOAL_LABELS.get(user["goal"] or "", user["goal"] or ""),
        "equipment": user["equipment"],
        "equipment_label": _EQUIPMENT_LABELS.get(user["equipment"] or "", user["equipment"] or ""),
        "days_per_week": user["days_per_week"],
        "goal_calories": user["goal_calories"],
        "goal_protein": user["goal_protein"],
        "goal_carbs": user["goal_carbs"],
        "goal_fat": user["goal_fat"],
        "total_workouts": stats["total_workouts"],
        "avg_rpe": round(avg_rpe, 1) if avg_rpe else 0,
        "nutrition_days_tracked": nutr_avg["days_tracked"],
        "utc_offset": utc_offset,
        "timezone_label": tz_str,
        "water_goal": user.get("water_goal") or 8,
        "water_interval": user.get("water_interval") or 2,
        "notif_water": bool(user.get("notif_water", 1)),
        "notif_breakfast": bool(user.get("notif_breakfast", 1)),
        "notif_workout": bool(user.get("notif_workout", 1)),
        "notif_evening": bool(user.get("notif_evening", 0)),
        "press_analysis_enabled": bool(user.get("press_analysis_enabled", 0)),
        "created_at": user.get("created_at", ""),
    }


class ProfileUpdateRequest(BaseModel):
    weight: float | None = Field(default=None, gt=0, lt=500)
    height: float | None = Field(default=None, gt=0, lt=300)
    age: int | None = Field(default=None, gt=0, lt=120)
    goal_calories: int | None = Field(default=None, gt=0)
    goal_protein: int | None = Field(default=None, gt=0)
    goal_carbs: int | None = Field(default=None, gt=0)
    goal_fat: int | None = Field(default=None, gt=0)
    water_goal: int | None = Field(default=None, ge=1, le=20)
    water_interval: int | None = Field(default=None, ge=1, le=6)
    notif_water: bool | None = None
    notif_breakfast: bool | None = None
    notif_workout: bool | None = None
    notif_evening: bool | None = None
    press_analysis_enabled: bool | None = None
    utc_offset: int | None = Field(default=None, ge=-12, le=14)


@app.patch("/api/profile")
async def profile_update(body: ProfileUpdateRequest, x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    raw = body.model_dump()
    updates = {}
    for k, v in raw.items():
        if v is None:
            continue
        if isinstance(v, bool):
            updates[k] = int(v)
        else:
            updates[k] = v
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    await update_user(user_id, **updates)
    return {"ok": True}


# ── Body / Тело ───────────────────────────────────────────────────────────────

@app.get("/api/body")
async def body_get(x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    weight_history = await get_weight_history(user_id, weeks=8)
    measurements = await get_latest_measurements(user_id)
    measurements_old = await get_measurements_month_ago(user_id)

    # BMI
    height_m = (user["height"] or 0) / 100
    weight = user["weight"] or 0
    bmi = round(weight / (height_m ** 2), 1) if height_m > 0 else None
    bmi_label = (
        "Дефицит" if bmi and bmi < 18.5 else
        "Норма" if bmi and bmi < 25 else
        "Избыток" if bmi and bmi < 30 else
        "Ожирение" if bmi else None
    )

    def delta(field):
        if not measurements or not measurements_old:
            return None
        cur = measurements.get(field)
        old = measurements_old.get(field)
        if cur is None or old is None:
            return None
        return round(cur - old, 1)

    return {
        "current_weight": weight,
        "weight_history": weight_history,
        "measurements": {
            "chest": measurements.get("chest") if measurements else None,
            "waist": measurements.get("waist") if measurements else None,
            "bicep": measurements.get("bicep") if measurements else None,
            "hips": measurements.get("hips") if measurements else None,
        },
        "deltas": {
            "chest": delta("chest"),
            "waist": delta("waist"),
            "bicep": delta("bicep"),
            "hips": delta("hips"),
        },
        "bmi": bmi,
        "bmi_label": bmi_label,
    }


class WeightLogRequest(BaseModel):
    weight: float = Field(gt=0, lt=500)


@app.post("/api/body/weight")
async def body_log_weight(body: WeightLogRequest, x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    await log_weight(user_id, today(), body.weight)
    await update_user(user_id, weight=body.weight)
    return {"ok": True, "weight": body.weight}


class MeasurementsRequest(BaseModel):
    chest: float | None = Field(default=None, gt=0)
    waist: float | None = Field(default=None, gt=0)
    bicep: float | None = Field(default=None, gt=0)
    hips: float | None = Field(default=None, gt=0)


@app.post("/api/body/measurements")
async def body_log_measurements(body: MeasurementsRequest, x_init_data: str = Header(alias="x-init-data")):
    user_id = validate_init_data(x_init_data)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No measurements provided")
    await log_measurements(user_id, today(), **updates)
    return {"ok": True}


MAX_VIDEO_SIZE = 20 * 1024 * 1024  # 20 МБ

_PENDING_DIR    = Path(QUEUE_DIR) / "pending"
_PROCESSING_DIR = Path(QUEUE_DIR) / "processing"
_DONE_DIR       = Path(QUEUE_DIR) / "done"


@app.post("/api/analyze_dumbbell_press")
async def analyze_dumbbell_press_endpoint(
    video: UploadFile = File(...),
    set_id: int | None = None,
    x_init_data: str = Header(alias="x-init-data"),
):
    tg_user_id = validate_init_data(x_init_data)

    data = await video.read(MAX_VIDEO_SIZE + 1)
    if len(data) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="Видео слишком большое — максимум 20 МБ")

    task_id = uuid.uuid4().hex
    ext = Path(video.filename or "video.mp4").suffix or ".mp4"
    video_path = str(Path(TEMP_VIDEO_DIR) / f"{task_id}{ext}")

    with open(video_path, "wb") as f:
        f.write(data)

    task = {
        "task_id":    task_id,
        "user_id":    tg_user_id,
        "set_id":     set_id,
        "video_path": video_path,
    }
    try:
        (_PENDING_DIR / f"{task_id}.json").write_text(
            json.dumps(task, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        os.remove(video_path)
        raise

    return {"task_id": task_id}


@app.get("/api/press_analysis_status/{task_id}")
async def press_analysis_status(task_id: str, x_init_data: str = Header(alias="x-init-data")):
    validate_init_data(x_init_data)

    # Допускаем только hex-символы — защита от path traversal
    if not all(c in "0123456789abcdef" for c in task_id) or len(task_id) != 32:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    done_file = _DONE_DIR / f"{task_id}.json"
    if done_file.exists():
        try:
            result = json.loads(done_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"status": "processing"}
        return {"status": "done", "result": result}

    if (_PROCESSING_DIR / f"{task_id}.json").exists():
        return {"status": "processing"}

    if (_PENDING_DIR / f"{task_id}.json").exists():
        return {"status": "pending"}

    return {"status": "not_found"}


_exercise_info_cache: dict[str, dict] = {}


@app.get("/api/exercise/info")
async def exercise_info_endpoint(name: str, x_init_data: str = Header(alias="x-init-data")):
    validate_init_data(x_init_data)
    if name in _exercise_info_cache:
        return _exercise_info_cache[name]
    import asyncio as _asyncio
    from services.ai_service import get_exercise_technique_brief, get_exercise_gif
    technique, image_url = await _asyncio.gather(
        get_exercise_technique_brief(name),
        get_exercise_gif(name),
        return_exceptions=True,
    )
    result = {
        "technique": technique if isinstance(technique, str) else None,
        "image_url": image_url if isinstance(image_url, str) else None,
    }
    # кэшируем только если оба поля получены — иначе повторим попытку
    if result["technique"] and result["image_url"]:
        _exercise_info_cache[name] = result
    return result
