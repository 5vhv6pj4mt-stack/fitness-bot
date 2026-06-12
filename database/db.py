import aiosqlite
from config import DB_PATH

# Нормализация названий упражнений: е → ё и сокращения → полные названия
_EYO_FIXES = {
    'лежа':   'лёжа',
    'лежу':   'лёжу',
    'подъем': 'подъём',
    'подъема':'подъёма',
    'жестк':  'жёстк',
    'тяжел':  'тяжёл',
}

_ALIAS_FIXES = {
    'Подтяг-я обр. хватом':        'Подтягивания обратным хватом',
    'Подтягивания обр. хватом':     'Подтягивания обратным хватом',
    'Бицепс (штанга) суперсет':     'Суперсет: Бицепс',
    'Бицепсовый сгиб':              'Суперсет: Бицепс',
    'Трицепс суперсет':             'Суперсет: Трицепс',
    'Трицепсовый расшир':           'Суперсет: Трицепс',
}

def normalize_exercise(name: str) -> str:
    """Приводит название упражнения к каноническому написанию."""
    if not name:
        return name
    # Сначала полные алиасы
    if name in _ALIAS_FIXES:
        return _ALIAS_FIXES[name]
    # Затем е → ё
    result = name
    for wrong, right in _EYO_FIXES.items():
        result = result.replace(wrong, right)
        result = result.replace(wrong.capitalize(), right.capitalize())
    return result


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                age INTEGER,
                height REAL,
                weight REAL DEFAULT 70,
                goal TEXT DEFAULT 'mass',
                experience TEXT DEFAULT 'intermediate',
                days_per_week INTEGER DEFAULT 3,
                equipment TEXT DEFAULT 'gym',
                injuries TEXT,
                goal_calories INTEGER DEFAULT 3300,
                goal_protein INTEGER DEFAULT 160,
                goal_carbs INTEGER DEFAULT 380,
                goal_fat INTEGER DEFAULT 90,
                current_week INTEGER DEFAULT 1,
                current_week_type TEXT DEFAULT 'strength',
                current_day_index INTEGER DEFAULT 0,
                onboarded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_program (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                week_type TEXT NOT NULL,
                day_type TEXT NOT NULL,
                order_num INTEGER DEFAULT 0,
                exercise TEXT NOT NULL,
                sets INTEGER,
                reps_range TEXT,
                weight REAL DEFAULT 0,
                rpe_range TEXT,
                rest TEXT
            )
        """)
        # миграции для существующих БД
        for col, definition in [
            ("age", "INTEGER"),
            ("height", "REAL"),
            ("goal", "TEXT DEFAULT 'mass'"),
            ("experience", "TEXT DEFAULT 'intermediate'"),
            ("days_per_week", "INTEGER DEFAULT 3"),
            ("equipment", "TEXT DEFAULT 'gym'"),
            ("injuries", "TEXT"),
            ("onboarded", "INTEGER DEFAULT 0"),
            ("utc_offset", "INTEGER DEFAULT 7"),
            ("water_goal", "INTEGER DEFAULT 8"),
            ("water_interval", "INTEGER DEFAULT 2"),
            ("notif_water", "INTEGER DEFAULT 1"),
            ("notif_breakfast", "INTEGER DEFAULT 1"),
            ("notif_workout", "INTEGER DEFAULT 1"),
            ("notif_evening", "INTEGER DEFAULT 0"),
            ("press_analysis_enabled", "INTEGER DEFAULT 0"),
            ("notify_pr", "INTEGER DEFAULT 1"),
            ("notify_streak", "INTEGER DEFAULT 1"),
            ("notify_plateau", "INTEGER DEFAULT 1"),
            ("notify_weekly_report", "INTEGER DEFAULT 1"),
            ("notify_morning_brief", "INTEGER DEFAULT 1"),
            ("morning_brief_hour", "INTEGER DEFAULT 8"),
            ("morning_brief_minute", "INTEGER DEFAULT 0"),
            ("brief_workout",   "INTEGER DEFAULT 1"),
            ("brief_yesterday", "INTEGER DEFAULT 1"),
            ("brief_nutrient",  "INTEGER DEFAULT 1"),
            ("brief_food_idea", "INTEGER DEFAULT 0"),
            ("brief_recovery",  "INTEGER DEFAULT 1"),
            ("brief_week_prog", "INTEGER DEFAULT 1"),
            ("brief_tip",       "INTEGER DEFAULT 1"),
            ("brief_water",     "INTEGER DEFAULT 1"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weight_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                weight REAL NOT NULL,
                UNIQUE(user_id, date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS body_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                chest REAL,
                waist REAL,
                bicep REAL,
                hips REAL,
                UNIQUE(user_id, date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS water_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                glasses INTEGER DEFAULT 0,
                UNIQUE(user_id, date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS food_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                calories REAL DEFAULT 0,
                protein REAL DEFAULT 0,
                carbs REAL DEFAULT 0,
                fat REAL DEFAULT 0,
                meal_type TEXT DEFAULT 'other',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            await db.execute("ALTER TABLE food_log ADD COLUMN meal_type TEXT DEFAULT 'other'")
            await db.commit()
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                day_type TEXT NOT NULL,
                week_number INTEGER,
                week_type TEXT,
                total_tonnage REAL DEFAULT 0,
                avg_rpe REAL DEFAULT 0,
                notes TEXT,
                is_finished INTEGER DEFAULT 0,
                ex_index INTEGER DEFAULT 0,
                set_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col in [
            ("is_finished",  "INTEGER DEFAULT 0"),
            ("ex_index",     "INTEGER DEFAULT 0"),
            ("set_index",    "INTEGER DEFAULT 0"),
            ("ai_analysis",  "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE workouts ADD COLUMN {col[0]} {col[1]}")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workout_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER NOT NULL,
                exercise TEXT NOT NULL,
                set_number INTEGER,
                planned_weight REAL,
                actual_weight REAL,
                reps INTEGER,
                rpe REAL,
                notes TEXT,
                FOREIGN KEY (workout_id) REFERENCES workouts(id)
            )
        """)
        try:
            await db.execute("ALTER TABLE workout_sets ADD COLUMN notes TEXT")
            await db.commit()
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meal_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                meal_id TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                UNIQUE(user_id, meal_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS food_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                calories REAL DEFAULT 0,
                protein REAL DEFAULT 0,
                carbs REAL DEFAULT 0,
                fat REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS db_press_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                set_id INTEGER,
                timestamp TEXT NOT NULL,
                left_angle REAL,
                right_angle REAL,
                depth TEXT,
                warnings TEXT,
                recommendation TEXT
            )
        """)
        await db.commit()


DEFAULT_MEALS = [
    {"id": "breakfast", "name": "Завтрак",   "hour": 8,  "minute": 30},
    {"id": "snack1",    "name": "Перекус 1", "hour": 11, "minute": 30},
    {"id": "lunch",     "name": "Обед",      "hour": 13, "minute": 30},
    {"id": "snack2",    "name": "Полдник",   "hour": 16, "minute": 30},
    {"id": "dinner",    "name": "Ужин",      "hour": 19, "minute": 30},
]


async def save_user_program(user_id: int, program: list[dict]):
    """Сохраняет программу тренировок пользователя. program — список упражнений."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_program WHERE user_id = ?", (user_id,))
        for ex in program:
            await db.execute("""
                INSERT INTO user_program (user_id, week_type, day_type, order_num, exercise, sets, reps_range, weight, rpe_range, rest)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (user_id, ex["week_type"], ex["day_type"], ex.get("order_num", 0),
                  normalize_exercise(ex["exercise"]), ex["sets"], ex["reps_range"],
                  ex.get("weight", 0), ex.get("rpe_range", ""), ex.get("rest", "1м30с")))
        await db.commit()


async def update_exercise_weight(user_id: int, week_type: str, day_type: str, exercise: str, new_weight: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE user_program SET weight=? WHERE user_id=? AND week_type=? AND day_type=? AND exercise=?",
            (new_weight, user_id, week_type, day_type, exercise)
        )
        await db.commit()


async def get_top_exercises(user_id: int, n: int = 6) -> list[str]:
    """Упражнения с наибольшим числом сессий (минимум 2)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT ws.exercise, COUNT(DISTINCT w.id) as sessions
            FROM workout_sets ws JOIN workouts w ON ws.workout_id=w.id
            WHERE w.user_id=? AND w.is_finished=1 AND ws.actual_weight >= 0
            GROUP BY ws.exercise HAVING sessions >= 2
            ORDER BY sessions DESC LIMIT ?
        ''', (user_id, n)) as cur:
            return [r[0] for r in await cur.fetchall()]


async def get_exercise_history(user_id: int, exercise: str, limit: int = 15) -> list[dict]:
    """Максимальный вес по упражнению за последние N сессий."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT w.date, MAX(ws.actual_weight) as max_weight
            FROM workout_sets ws JOIN workouts w ON ws.workout_id=w.id
            WHERE w.user_id=? AND ws.exercise=? AND w.is_finished=1 AND ws.actual_weight >= 0
            GROUP BY w.id, w.date ORDER BY w.date DESC LIMIT ?
        ''', (user_id, exercise, limit)) as cur:
            rows = await cur.fetchall()
            return [{"date": r[0], "max_weight": r[1]} for r in reversed(rows)]


async def get_user_program(user_id: int, week_type: str, day_type: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_program WHERE user_id=? AND week_type=? AND day_type=? ORDER BY order_num",
            (user_id, week_type, day_type)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_user_day_types(user_id: int, week_type: str) -> list[str]:
    """Возвращает уникальные типы дней для пользователя в данной неделе."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT day_type FROM user_program WHERE user_id=? AND week_type=? GROUP BY day_type ORDER BY MIN(id)",
            (user_id, week_type)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_user_week_types(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT week_type FROM user_program WHERE user_id=?",
            (user_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_onboarded_users() -> list[int]:
    """Возвращает user_id всех зарегистрированных пользователей."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE onboarded = 1") as cur:
            return [r[0] for r in await cur.fetchall()]


async def create_user(user_id: int, name: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        await db.commit()
    return await get_user(user_id)


_ALLOWED_USER_FIELDS = {
    "name", "age", "weight", "height",
    "goal", "experience", "days_per_week", "equipment", "injuries",
    "goal_calories", "goal_protein", "goal_carbs", "goal_fat",
    "current_week", "current_week_type", "current_day_index",
    "onboarded", "utc_offset",
    "water_goal", "water_interval",
    "notif_water", "notif_breakfast", "notif_workout", "notif_evening",
    "notify_pr", "notify_streak", "notify_plateau", "notify_weekly_report",
    "notify_morning_brief", "morning_brief_hour", "morning_brief_minute",
    "press_analysis_enabled",
    "brief_workout", "brief_yesterday", "brief_nutrient", "brief_food_idea",
    "brief_recovery", "brief_week_prog", "brief_tip", "brief_water",
}

async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    invalid = set(kwargs.keys()) - _ALLOWED_USER_FIELDS
    if invalid:
        raise ValueError(f"update_user: недопустимые поля: {invalid}")
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
        await db.commit()


async def reset_user_cycle(user_id: int):
    """Сбрасывает цикл тренировок пользователя на начальные значения."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET current_week=1, current_week_type='strength', current_day_index=0 WHERE user_id=?",
            (user_id,)
        )
        await db.commit()


async def delete_user_program(user_id: int):
    """Удаляет всю программу тренировок пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_program WHERE user_id=?", (user_id,))
        await db.commit()


async def log_food(user_id: int, date: str, description: str,
                   calories: float, protein: float, carbs: float, fat: float,
                   meal_type: str = 'other') -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO food_log (user_id, date, description, calories, protein, carbs, fat, meal_type) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, date, description, calories, protein, carbs, fat, meal_type)
        )
        await db.commit()
        return cur.lastrowid


async def get_day_nutrition(user_id: int, date: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT SUM(calories), SUM(protein), SUM(carbs), SUM(fat) FROM food_log WHERE user_id=? AND date=?",
            (user_id, date)
        ) as cur:
            row = await cur.fetchone()
            return {
                "calories": row[0] or 0,
                "protein": row[1] or 0,
                "carbs": row[2] or 0,
                "fat": row[3] or 0,
            }


async def get_day_food_entries(user_id: int, date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM food_log WHERE user_id=? AND date=? ORDER BY created_at ASC",
            (user_id, date)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def was_workout_done_today(user_id: int, date_str: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM workouts WHERE user_id=? AND date=? AND is_finished=1 LIMIT 1",
            (user_id, date_str)
        ) as cur:
            return await cur.fetchone() is not None


async def was_food_logged_recently(user_id: int, minutes: int = 30) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM food_log WHERE user_id=? AND created_at >= datetime('now', ? || ' minutes') LIMIT 1",
            (user_id, f"-{minutes}")
        ) as cur:
            return await cur.fetchone() is not None


async def create_workout(user_id: int, date: str, day_type: str,
                          week_number: int, week_type: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO workouts (user_id, date, day_type, week_number, week_type) VALUES (?,?,?,?,?)",
            (user_id, date, day_type, week_number, week_type)
        )
        await db.commit()
        return cur.lastrowid


async def save_set(workout_id: int, exercise: str, set_number: int,
                   planned_weight: float, actual_weight: float, reps: int, rpe: float, notes: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO workout_sets (workout_id, exercise, set_number, planned_weight, actual_weight, reps, rpe, notes) VALUES (?,?,?,?,?,?,?,?)",
            (workout_id, normalize_exercise(exercise), set_number, planned_weight, actual_weight, reps, rpe, notes)
        )
        await db.commit()
        return cur.lastrowid


async def finish_workout(workout_id: int, total_tonnage: float, avg_rpe: float, notes: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workouts SET total_tonnage=?, avg_rpe=?, notes=?, is_finished=1 WHERE id=?",
            (total_tonnage, avg_rpe, notes, workout_id)
        )
        await db.commit()


async def get_workout_by_id(workout_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM workouts WHERE id=?", (workout_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_active_workout(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workouts WHERE user_id=? AND is_finished=0 ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_workout_progress(workout_id: int, ex_index: int, set_index: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workouts SET ex_index=?, set_index=? WHERE id=?",
            (ex_index, set_index, workout_id)
        )
        await db.commit()


async def discard_all_active_workouts(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workouts SET is_finished=1 WHERE user_id=? AND is_finished=0",
            (user_id,)
        )
        await db.commit()


async def get_last_workout_by_day(user_id: int, day_type: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workouts WHERE user_id=? AND day_type=? AND is_finished=1 ORDER BY date DESC LIMIT 1",
            (user_id, day_type)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def save_workout_analysis(workout_id: int, analysis: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workouts SET ai_analysis=? WHERE id=?",
            (analysis, workout_id)
        )
        await db.commit()


async def get_workout_analysis(workout_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT ai_analysis FROM workouts WHERE id=?",
            (workout_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def get_last_workouts(user_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workouts WHERE user_id=? AND is_finished=1 ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_week_workout_count(user_id: int, from_date: str) -> int:
    """Число завершённых тренировок начиная с from_date (YYYY-MM-DD)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM workouts WHERE user_id=? AND is_finished=1 AND date>=?",
            (user_id, from_date)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_workout_sets(workout_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workout_sets WHERE workout_id=? ORDER BY set_number",
            (workout_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_workout_set(set_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM workout_sets WHERE id=?", (set_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_workout_set(set_id: int, weight: float, reps: int, rpe: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workout_sets SET actual_weight=?, reps=?, rpe=? WHERE id=?",
            (weight, reps, rpe, set_id)
        )
        await db.commit()


async def update_workout_set(set_id: int, actual_weight: float, reps: int, rpe: float, notes: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workout_sets SET actual_weight=?, reps=?, rpe=?, notes=? WHERE id=?",
            (actual_weight, reps, rpe, notes, set_id)
        )
        await db.commit()


async def delete_workout_set(set_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM workout_sets WHERE id=?", (set_id,))
        await db.commit()


async def recalculate_workout_totals(workout_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT actual_weight, reps, rpe FROM workout_sets WHERE workout_id=?",
            (workout_id,)
        ) as cur:
            sets = await cur.fetchall()
        tonnage = sum(s[0] * s[1] for s in sets) if sets else 0
        avg_rpe = sum(s[2] for s in sets) / len(sets) if sets else 0
        await db.execute(
            "UPDATE workouts SET total_tonnage=?, avg_rpe=? WHERE id=?",
            (tonnage, avg_rpe, workout_id)
        )
        await db.commit()


async def get_recent_workouts(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workouts WHERE user_id=? AND is_finished=1 ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_last_workouts_rich(user_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT w.*, COUNT(s.id) as set_count
               FROM workouts w
               LEFT JOIN workout_sets s ON s.workout_id = w.id
               WHERE w.user_id=? AND w.is_finished=1 AND w.total_tonnage > 0
               GROUP BY w.id ORDER BY w.date DESC LIMIT ?""",
            (user_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_time_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_tonnage), 0) FROM workouts WHERE user_id=? AND is_finished=1 AND total_tonnage > 0",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return {"total_workouts": row[0] or 0, "total_tonnage": row[1] or 0}


async def get_workout_streak(user_id: int) -> dict:
    """Считает текущий стрик тренировок.
    Стрик = последовательные тренировки без перерыва > 12 дней.
    Возвращает: {current, longest, last_date}
    """
    from datetime import datetime, timedelta
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT date FROM workouts WHERE user_id=? AND is_finished=1 ORDER BY date DESC",
            (user_id,)
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        return {"current": 0, "longest": 0, "last_date": None}

    dates = sorted({r[0] for r in rows}, reverse=True)
    MAX_GAP = 12  # дней

    # Текущий стрик
    current = 1
    for i in range(len(dates) - 1):
        d1 = datetime.strptime(dates[i], "%Y-%m-%d")
        d2 = datetime.strptime(dates[i + 1], "%Y-%m-%d")
        if (d1 - d2).days <= MAX_GAP:
            current += 1
        else:
            break

    # Проверяем не устарел ли стрик (последняя тренировка > 12 дней назад)
    last = datetime.strptime(dates[0], "%Y-%m-%d")
    days_since = (datetime.utcnow() - last).days
    if days_since > MAX_GAP:
        current = 0

    # Longest streak
    longest = 1
    run = 1
    for i in range(len(dates) - 1):
        d1 = datetime.strptime(dates[i], "%Y-%m-%d")
        d2 = datetime.strptime(dates[i + 1], "%Y-%m-%d")
        if (d1 - d2).days <= MAX_GAP:
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    return {"current": current, "longest": longest, "last_date": dates[0]}


async def get_plateau_exercises(user_id: int) -> list[dict]:
    """Упражнения в плато: 3+ тренировки подряд с одинаковым весом."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT DISTINCT s.exercise
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.actual_weight > 0""",
            (user_id,)
        ) as cur:
            exercises = [r[0] for r in await cur.fetchall()]

    plateaus = []
    async with aiosqlite.connect(DB_PATH) as db:
        for ex in exercises:
            async with db.execute(
                """SELECT MAX(s.actual_weight) as max_w, AVG(s.rpe) as avg_rpe
                   FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
                   WHERE w.user_id=? AND w.is_finished=1 AND s.exercise=? AND s.actual_weight > 0
                   GROUP BY w.id ORDER BY w.date DESC LIMIT 4""",
                (user_id, ex)
            ) as cur:
                sessions = await cur.fetchall()

            if len(sessions) < 3:
                continue
            weights = [r[0] for r in sessions[:3]]
            avg_rpe = sum(r[1] or 8.0 for r in sessions[:3]) / 3
            if len(set(weights)) == 1:
                plateaus.append({"exercise": ex, "weight": weights[0], "sessions": 3, "avg_rpe": avg_rpe})

    return plateaus


async def get_exercise_prs(user_id: int, limit: int = 6) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT s.exercise, MAX(s.actual_weight) as max_weight, s.reps
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.actual_weight >= 0
               GROUP BY s.exercise ORDER BY max_weight DESC LIMIT ?""",
            (user_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_nutrition_week_avg(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT COUNT(DISTINCT date), AVG(cal), AVG(prot), AVG(carb), AVG(fat)
               FROM (
                   SELECT date, SUM(calories) as cal, SUM(protein) as prot,
                          SUM(carbs) as carb, SUM(fat) as fat
                   FROM food_log
                   WHERE user_id=? AND date >= date('now', '-6 days')
                   GROUP BY date
               )""",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return {
                "days_tracked": row[0] or 0, "avg_calories": row[1] or 0,
                "avg_protein":  row[2] or 0, "avg_carbs":    row[3] or 0,
                "avg_fat":      row[4] or 0,
            }


async def get_meal_reminders(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT meal_id, enabled, hour, minute FROM meal_reminders WHERE user_id=?",
            (user_id,)
        ) as cur:
            saved = {r["meal_id"]: dict(r) for r in await cur.fetchall()}
    result = []
    for m in DEFAULT_MEALS:
        s = saved.get(m["id"], {})
        result.append({
            "meal_id": m["id"], "name": m["name"],
            "enabled": s.get("enabled", 1),
            "hour": s.get("hour", m["hour"]),
            "minute": s.get("minute", m["minute"]),
        })
    return result


async def set_meal_reminder(user_id: int, meal_id: str, enabled: int, hour: int, minute: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO meal_reminders (user_id, meal_id, enabled, hour, minute) VALUES (?,?,?,?,?)
               ON CONFLICT(user_id, meal_id) DO UPDATE SET
               enabled=excluded.enabled, hour=excluded.hour, minute=excluded.minute""",
            (user_id, meal_id, enabled, hour, minute)
        )
        await db.commit()


async def get_food_entry(entry_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM food_log WHERE id=?", (entry_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_food_entry(entry_id: int, description: str, calories: float,
                             protein: float, carbs: float, fat: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE food_log SET description=?, calories=?, protein=?, carbs=?, fat=? WHERE id=?",
            (description, calories, protein, carbs, fat, entry_id)
        )
        await db.commit()


async def delete_food_entry(entry_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM food_log WHERE id=?", (entry_id,))
        await db.commit()


async def get_water_today(user_id: int, date: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT glasses FROM water_log WHERE user_id=? AND date=?", (user_id, date)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def add_water_glass(user_id: int, date: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO water_log (user_id, date, glasses) VALUES (?,?,1) "
            "ON CONFLICT(user_id, date) DO UPDATE SET glasses = glasses + 1",
            (user_id, date),
        )
        await db.commit()
        async with db.execute(
            "SELECT glasses FROM water_log WHERE user_id=? AND date=?", (user_id, date)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 1


async def log_weight(user_id: int, date: str, weight: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO weight_log (user_id, date, weight) VALUES (?,?,?) "
            "ON CONFLICT(user_id, date) DO UPDATE SET weight=excluded.weight",
            (user_id, date, weight),
        )
        await db.commit()


async def get_weight_history(user_id: int, weeks: int = 8) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT date, weight FROM weight_log
               WHERE user_id=? AND date >= date('now', ? || ' days')
               ORDER BY date ASC""",
            (user_id, -(weeks * 7)),
        ) as cur:
            return [{"date": r[0], "weight": r[1]} for r in await cur.fetchall()]


async def log_measurements(user_id: int, date: str, **kwargs):
    fields = [k for k in ("chest", "waist", "bicep", "hips") if k in kwargs]
    if not fields:
        return
    sets = ", ".join(f"{f}=excluded.{f}" for f in fields)
    cols = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    vals = [kwargs[f] for f in fields]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT INTO body_measurements (user_id, date, {cols}) VALUES (?,?,{placeholders}) "
            f"ON CONFLICT(user_id, date) DO UPDATE SET {sets}",
            [user_id, date] + vals,
        )
        await db.commit()


async def get_latest_measurements(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM body_measurements WHERE user_id=? ORDER BY date DESC LIMIT 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_measurements_month_ago(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM body_measurements WHERE user_id=?
               AND date <= date('now', '-28 days') ORDER BY date DESC LIMIT 1""",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


_MEAL_DEFAULTS = {
    "breakfast": ["Овсянка на молоке", "Яичница 3 яйца", "Омлет с овощами", "Творог 200г", "Греческий йогурт с ягодами"],
    "lunch":     ["Куриная грудка с рисом", "Гречка с говядиной", "Борщ", "Лосось с овощами", "Паста с курицей"],
    "snack":     ["Банан", "Протеиновый коктейль", "Орехи 30г", "Творог 150г", "Яблоко + арахисовая паста"],
    "dinner":    ["Куриная грудка на гриле", "Рыба на пару", "Омлет белковый", "Творог с ягодами", "Греческий салат с тунцом"],
}


async def get_meal_suggestions(user_id: int, meal_type: str, limit: int = 8) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Yesterday's same meal
        async with db.execute(
            """
            SELECT description, calories, protein, carbs, fat
            FROM food_log
            WHERE user_id=? AND meal_type=? AND date=date('now','-1 day')
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, meal_type, limit),
        ) as cur:
            yesterday = [dict(r) for r in await cur.fetchall()]

        seen = {r["description"].lower() for r in yesterday}

        # Frequent for this meal_type
        async with db.execute(
            """
            SELECT description,
                   ROUND(AVG(calories)) as calories,
                   ROUND(AVG(protein),1) as protein,
                   ROUND(AVG(carbs),1) as carbs,
                   ROUND(AVG(fat),1) as fat,
                   COUNT(*) as freq
            FROM food_log
            WHERE user_id=? AND meal_type=? AND date >= date('now','-30 days')
            GROUP BY lower(description)
            ORDER BY freq DESC LIMIT ?
            """,
            (user_id, meal_type, limit),
        ) as cur:
            frequent = [dict(r) for r in await cur.fetchall() if r["description"].lower() not in seen]

        result = yesterday + frequent
        if not result:
            for desc in _MEAL_DEFAULTS.get(meal_type, _MEAL_DEFAULTS["snack"])[:limit]:
                result.append({"description": desc, "calories": None, "protein": None, "carbs": None, "fat": None})
        return result[:limit]


async def get_frequent_foods(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT description,
                   ROUND(AVG(calories)) as calories,
                   ROUND(AVG(protein), 1) as protein,
                   ROUND(AVG(carbs), 1) as carbs,
                   ROUND(AVG(fat), 1) as fat,
                   COUNT(*) as freq
            FROM food_log
            WHERE user_id=?
              AND date >= date('now', '-30 days')
            GROUP BY lower(description)
            ORDER BY freq DESC
            LIMIT ?
            """,
            (user_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_food_log_dates(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT date FROM food_log WHERE user_id=? ORDER BY date DESC LIMIT 14",
            (user_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def get_workout_set(set_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM workout_sets WHERE id=?", (set_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def save_food_template(user_id: int, name: str, description: str,
                              calories: float, protein: float, carbs: float, fat: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO food_templates (user_id, name, description, calories, protein, carbs, fat) VALUES (?,?,?,?,?,?,?)",
            (user_id, name, description, calories, protein, carbs, fat)
        )
        await db.commit()


async def get_food_templates(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM food_templates WHERE user_id=? ORDER BY created_at DESC",
            (user_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_food_template(template_id: int, user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM food_templates WHERE id=? AND user_id=?",
            (template_id, user_id)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def delete_food_template(template_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM food_templates WHERE id=? AND user_id=?", (template_id, user_id))
        await db.commit()


async def get_tonnage_by_weeks(user_id: int, n_weeks: int = 8) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT strftime('%Y-W%W', date) as week_label, SUM(total_tonnage) as tonnage
               FROM workouts
               WHERE user_id=? AND is_finished=1 AND date >= date('now', ? || ' days')
               GROUP BY week_label ORDER BY week_label""",
            (user_id, f"-{n_weeks * 7}")
        ) as cur:
            return [{"week_label": r[0], "tonnage": r[1] or 0} for r in await cur.fetchall()]


async def get_best_sets_for_1rm(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT s.exercise, s.actual_weight as weight, s.reps
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.reps BETWEEN 1 AND 12
               ORDER BY s.exercise""",
            (user_id,)
        ) as cur:
            return [{"exercise": r[0], "weight": r[1], "reps": r[2]} for r in await cur.fetchall()]


async def get_muscle_volume(user_id: int, days: int = 28) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT s.exercise, SUM(s.actual_weight * s.reps) as volume
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.actual_weight >= 0
                 AND w.date >= date('now', ? || ' days')
               GROUP BY s.exercise""",
            (user_id, f"-{days}")
        ) as cur:
            return [{"exercise": r[0], "volume": r[1]} for r in await cur.fetchall()]


async def get_week_workouts(user_id: int, week_start: str, week_end: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workouts WHERE user_id=? AND is_finished=1 AND date BETWEEN ? AND ? ORDER BY date",
            (user_id, week_start, week_end)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_week_nutrition_avg(user_id: int, week_start: str, week_end: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT COUNT(DISTINCT date), AVG(cal), AVG(prot), AVG(carb), AVG(fat)
               FROM (
                   SELECT date, SUM(calories) as cal, SUM(protein) as prot,
                          SUM(carbs) as carb, SUM(fat) as fat
                   FROM food_log WHERE user_id=? AND date BETWEEN ? AND ?
                   GROUP BY date
               )""",
            (user_id, week_start, week_end)
        ) as cur:
            row = await cur.fetchone()
            return {
                "days_tracked": row[0] or 0, "avg_calories": row[1] or 0,
                "avg_protein":  row[2] or 0, "avg_carbs":    row[3] or 0,
                "avg_fat":      row[4] or 0,
            }


async def get_daily_nutrition_7d(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT date, SUM(calories) FROM food_log
               WHERE user_id=? AND date >= date('now', '-6 days')
               GROUP BY date""",
            (user_id,)
        ) as cur:
            return {r[0]: r[1] for r in await cur.fetchall()}


async def get_avg_rpe_recent(user_id: int, limit: int = 10) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT AVG(avg_rpe) FROM (
               SELECT avg_rpe FROM workouts
               WHERE user_id=? AND is_finished=1 AND avg_rpe > 0
               ORDER BY date DESC LIMIT ?)""",
            (user_id, limit)
        ) as cur:
            row = await cur.fetchone()
            return round(row[0] or 0, 1)


async def get_last_exercise_set(user_id: int, exercise: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT s.actual_weight, s.reps, s.rpe
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.exercise=? AND s.actual_weight >= 0
               ORDER BY w.date DESC, s.actual_weight DESC
               LIMIT 1""",
            (user_id, exercise),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_exercise_weight_history(user_id: int, exercise: str, limit: int = 8) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT w.date, MAX(s.actual_weight) as weight
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.exercise=? AND s.actual_weight >= 0
               GROUP BY w.id ORDER BY w.date DESC LIMIT ?""",
            (user_id, exercise, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [{"date": r[0], "weight": r[1]} for r in reversed(rows)]


async def get_user_exercises(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT DISTINCT s.exercise
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.actual_weight >= 0
               ORDER BY s.exercise""",
            (user_id,)
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def get_week_exercise_weights(user_id: int, week_start: str, week_end: str) -> dict[str, float]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT s.exercise, MAX(s.actual_weight)
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND w.date BETWEEN ? AND ? AND s.actual_weight >= 0
               GROUP BY s.exercise""",
            (user_id, week_start, week_end)
        ) as cur:
            return {r[0]: r[1] for r in await cur.fetchall()}


async def get_weekly_new_prs(user_id: int, week_start: str, week_end: str) -> list[dict]:
    """Упражнения, где вес за неделю равен all-time рекорду (новый ПР)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT s.exercise, MAX(s.actual_weight) as week_max
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1
                 AND w.date BETWEEN ? AND ? AND s.actual_weight > 0
               GROUP BY s.exercise""",
            (user_id, week_start, week_end)
        ) as cur:
            week_weights = {r[0]: r[1] for r in await cur.fetchall()}

        if not week_weights:
            return []

        prs = []
        for exercise, week_max in week_weights.items():
            async with db.execute(
                """SELECT MAX(s.actual_weight)
                   FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
                   WHERE w.user_id=? AND w.is_finished=1 AND s.exercise=? AND s.actual_weight > 0""",
                (user_id, exercise)
            ) as cur:
                row = await cur.fetchone()
                all_time_max = row[0] if row else 0
            if week_max >= (all_time_max or 0):
                prs.append({"exercise": exercise, "weight": week_max})
        return prs


async def get_weekly_kbju_days_in_norm(user_id: int, week_start: str, week_end: str,
                                        tolerance: float = 0.2) -> int:
    """Количество дней, когда калории были в пределах ±tolerance от цели."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT goal_calories FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            goal = (row[0] or 0) if row else 0
        if not goal:
            return 0
        async with db.execute(
            """SELECT date, SUM(calories) as total_cal
               FROM food_log
               WHERE user_id=? AND date BETWEEN ? AND ?
               GROUP BY date""",
            (user_id, week_start, week_end)
        ) as cur:
            days = await cur.fetchall()
        lo, hi = goal * (1 - tolerance), goal * (1 + tolerance)
        return sum(1 for _, cal in days if lo <= (cal or 0) <= hi)


async def save_press_analysis(
    user_id: int,
    set_id: int | None,
    left_angle: float,
    right_angle: float,
    depth: str,
    warnings: dict,
    recommendation: str,
) -> int:
    import json as _json
    from datetime import datetime
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO db_press_analyses
               (user_id, set_id, timestamp, left_angle, right_angle, depth, warnings, recommendation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                set_id,
                datetime.utcnow().isoformat(),
                left_angle,
                right_angle,
                depth,
                _json.dumps(warnings, ensure_ascii=False),
                recommendation,
            ),
        )
        await db.commit()
        return cur.lastrowid


async def check_exercise_pr(user_id: int, exercise: str, weight: float, reps: int, current_workout_id: int) -> str | None:
    """Проверяет PR после подхода. Возвращает тип: 'weight'|'1rm'|None.
    1RM по формуле Эпли: weight * (1 + reps/30).
    """
    new_1rm = weight * (1 + reps / 30.0)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT MAX(s.actual_weight), MAX(s.actual_weight * (1 + s.reps / 30.0))
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.exercise=?
                 AND s.actual_weight > 0 AND w.id != ?""",
            (user_id, exercise, current_workout_id),
        ) as cur:
            row = await cur.fetchone()
    if not row or row[0] is None:
        return None
    best_weight, best_1rm = row
    if weight > best_weight:
        return "weight"
    if new_1rm > (best_1rm or 0) + 0.5:
        return "1rm"
    return None


async def get_exercise_progression_hint(user_id: int, exercise: str) -> dict:
    """Анализирует последние 4 тренировки упражнения и возвращает рекомендацию по весу.
    Возвращает: {weight, action: 'increase'|'hold'|'decrease'|'aggressive', reason}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT w.id, w.date, MAX(s.actual_weight) as max_weight,
                      AVG(s.rpe) as avg_rpe
               FROM workout_sets s JOIN workouts w ON w.id = s.workout_id
               WHERE w.user_id=? AND w.is_finished=1 AND s.exercise=? AND s.actual_weight > 0
               GROUP BY w.id ORDER BY w.date DESC LIMIT 4""",
            (user_id, exercise),
        ) as cur:
            sessions = [dict(r) for r in await cur.fetchall()]

    if not sessions:
        return {}

    latest = sessions[0]
    w = latest["max_weight"]
    rpe = latest["avg_rpe"] or 8.0

    if len(sessions) >= 3:
        weights = [s["max_weight"] for s in sessions[:3]]
        rpes = [s["avg_rpe"] or 8.0 for s in sessions[:3]]
        stagnant = len(set(weights)) == 1
        avg_rpe_3 = sum(rpes) / len(rpes)

        if stagnant and avg_rpe_3 <= 7.5:
            return {"weight": w + 5.0, "action": "aggressive",
                    "reason": f"3 тренировки подряд {w:.1f}кг, RPE {avg_rpe_3:.1f} — время прибавить смелее"}
        if stagnant and avg_rpe_3 <= 8.5:
            return {"weight": w + 2.5, "action": "increase",
                    "reason": f"3 тренировки подряд {w:.1f}кг — пора добавить"}

    if rpe <= 7.5:
        return {"weight": w + 2.5, "action": "increase", "reason": f"RPE {rpe:.1f} — легко, повышаем"}
    if rpe <= 8.5:
        return {"weight": w, "action": "hold", "reason": f"RPE {rpe:.1f} — оптимально, держим вес"}
    if rpe <= 9.5:
        return {"weight": w, "action": "hold", "reason": f"RPE {rpe:.1f} — тяжело, закрепляем вес"}
    return {"weight": max(w - 2.5, 2.5), "action": "decrease", "reason": f"RPE {rpe:.1f} — слишком тяжело, снижаем"}