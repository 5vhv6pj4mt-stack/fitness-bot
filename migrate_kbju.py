"""
Миграция: пересчёт целей КБЖУ для всех пользователей через Claude.
Запуск: python migrate_kbju.py
"""
import asyncio
import aiosqlite
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
import os, json

load_dotenv()
DB_PATH = "fitness.db"
claude = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

GOAL_LABELS = {
    "mass":     "набор мышечной массы (профицит 200-400 ккал)",
    "loss":     "снижение жировой массы (дефицит 300-500 ккал)",
    "strength": "развитие максимальной силы (поддерживающие калории)",
    "tone":     "улучшение композиции тела (небольшой дефицит или поддержание)",
}
EXP_ACTIVITY = {
    "beginner":     1.375,
    "intermediate": 1.55,
    "advanced":     1.725,
}


async def calc_kbju(user: dict) -> dict | None:
    age    = user.get("age") or 25
    weight = user.get("weight") or 75
    height = user.get("height") or 175
    goal   = user.get("goal") or "mass"
    exp    = user.get("experience") or "intermediate"
    days   = user.get("days_per_week") or 3

    # Mifflin-St Jeor (мужчина по умолчанию)
    bmr = 10 * weight + 6.25 * height - 5 * age + 5
    activity = EXP_ACTIVITY.get(exp, 1.55)
    tdee = bmr * activity

    prompt = f"""Рассчитай цели КБЖУ для атлета.

Данные:
- Возраст: {age} лет, Вес: {weight} кг, Рост: {height} см
- Цель: {GOAL_LABELS.get(goal, goal)}
- Опыт: {exp}, Тренировок в неделю: {days}
- Расчётный TDEE (Mifflin-St Jeor): {tdee:.0f} ккал

Верни ТОЛЬКО JSON (целые числа):
{{"calories": число, "protein": число, "carbs": число, "fat": число}}

Правила:
- Белок: 1.8-2.2 г/кг веса тела
- Жиры: 0.8-1.0 г/кг веса тела
- Углеводы: остаток калорий после белка и жиров
- При наборе: +250 ккал к TDEE, при похудении: -400 ккал, при силе/тонусе: TDEE"""

    resp = await claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        system="Ты спортивный нутрициолог. Возвращай ТОЛЬКО JSON.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    return json.loads(text)


async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, name, age, weight, height, goal, experience, days_per_week "
            "FROM users WHERE onboarded = 1"
        ) as cur:
            users = await cur.fetchall()

    if not users:
        print("Нет пользователей для обновления.")
        return

    print(f"Найдено {len(users)} пользователей.")

    async with aiosqlite.connect(DB_PATH) as db:
        for u in users:
            user = dict(u)
            try:
                kbju = await calc_kbju(user)
                await db.execute(
                    """UPDATE users SET
                        goal_calories = ?, goal_protein = ?, goal_carbs = ?, goal_fat = ?
                       WHERE user_id = ?""",
                    (kbju["calories"], kbju["protein"], kbju["carbs"], kbju["fat"], user["user_id"])
                )
                await db.commit()
                print(f"  ✅ {user['name']} (id={user['user_id']}): "
                      f"{kbju['calories']} ккал | Б{kbju['protein']} У{kbju['carbs']} Ж{kbju['fat']}")
            except Exception as e:
                print(f"  ❌ {user['name']} (id={user['user_id']}): {e}")

    print("\nГотово.")


if __name__ == "__main__":
    asyncio.run(main())
