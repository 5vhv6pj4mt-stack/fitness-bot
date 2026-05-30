"""Загружает программу Кирилла в БД и помечает его как onboarded."""
import asyncio
from database.db import init_db, create_user, update_user, save_user_program, get_user

KIRILL_TG_ID = None  # заполнится автоматически при первом /start

async def load():
    await init_db()
    from database.program_data import PROGRAM

    program_flat = []
    for week_type, days in PROGRAM.items():
        for day_type, exercises in days.items():
            for i, ex in enumerate(exercises):
                program_flat.append({
                    "week_type": week_type,
                    "day_type": day_type,
                    "order_num": i,
                    "exercise": ex["exercise"],
                    "sets": ex["sets"],
                    "reps_range": ex["reps"],
                    "weight": ex["weight"],
                    "rpe_range": ex["rpe"],
                    "rest": ex["rest"],
                })

    print(f"Всего упражнений в программе: {len(program_flat)}")
    print("Программа готова к загрузке. Запустится автоматически при первом /start Кирилла.")
    return program_flat

if __name__ == "__main__":
    asyncio.run(load())
