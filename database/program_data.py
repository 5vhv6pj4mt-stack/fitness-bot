"""
Программа тренировок Кирилла. 3-недельный микроцикл: Силовая → Объёмная → Разгрузочная.
3 дня: Верх-Сила, Ноги, Верх-Объём.
"""

WEEK_TYPES = {
    "strength": "Силовая",
    "volume": "Объёмная",
    "deload": "Разгрузочная",
}

DAY_TYPES = {
    "upper_strength": "Верх — Сила",
    "legs": "Ноги",
    "upper_volume": "Верх — Объём",
}

# Порядок дней в цикле
DAY_SEQUENCE = ["upper_strength", "legs", "upper_volume"]

# Формат: { week_type: { day_type: [ {exercise, sets, reps_range, weight, rpe_range, rest} ] } }
PROGRAM = {
    "strength": {
        "upper_strength": [
            {"exercise": "Жим штанги наклонной", "sets": 4, "reps": "6–8", "weight": 50.0, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Тяга штанги в наклоне", "sets": 3, "reps": "6–8", "weight": 47.5, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Армейский жим сидя", "sets": 3, "reps": "6–8", "weight": 20.0, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Подтягивания широкие с весом", "sets": 3, "reps": "4–6", "weight": 5.0, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Тяга лица", "sets": 3, "reps": "15–20", "weight": 42.0, "rpe": "8–8.5", "rest": "2м30с"},
        ],
        "legs": [
            {"exercise": "Жим ногами", "sets": 4, "reps": "6–8", "weight": 150.0, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Болгарские выпады", "sets": 3, "reps": "6–8", "weight": 37.5, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Румынская тяга", "sets": 3, "reps": "6–8", "weight": 50.0, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Сгибания ног", "sets": 3, "reps": "8–10", "weight": 45.0, "rpe": "8–8.5", "rest": "2м30с"},
            {"exercise": "Подъём на носки", "sets": 4, "reps": "8–12", "weight": 50.0, "rpe": "8–8.5", "rest": "2м30с"},
            {"exercise": "Пресс", "sets": 3, "reps": "15–20", "weight": 0.0, "rpe": "7–8", "rest": "1м"},
        ],
        "upper_volume": [
            {"exercise": "Подтягивания обратным хватом с весом", "sets": 3, "reps": "4–6", "weight": 5.0, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Жим гантелей лёжа", "sets": 4, "reps": "6–8", "weight": 42.5, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Тяга горизонтального блока", "sets": 3, "reps": "6–8", "weight": 42.5, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Бицепс (штанга) суперсет", "sets": 3, "reps": "6–8", "weight": 27.5, "rpe": "8.5–9", "rest": "—"},
            {"exercise": "Трицепс суперсет", "sets": 3, "reps": "6–8", "weight": 20.0, "rpe": "8.5–9", "rest": "2м30с"},
            {"exercise": "Обратная бабочка", "sets": 3, "reps": "10–12", "weight": 15.0, "rpe": "8–8.5", "rest": "1м30с"},
            {"exercise": "Вис на перекладине", "sets": 3, "reps": "макс. сек.", "weight": 0.0, "rpe": "—", "rest": "1м"},
        ],
    },
    "volume": {
        "upper_strength": [
            {"exercise": "Жим штанги наклонной", "sets": 4, "reps": "12–15", "weight": 35.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Тяга штанги в наклоне", "sets": 3, "reps": "12–15", "weight": 32.5, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Армейский жим сидя", "sets": 3, "reps": "12–15", "weight": 15.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Подтягивания широкие с весом", "sets": 3, "reps": "10–12", "weight": 0.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Тяга лица", "sets": 3, "reps": "15–20", "weight": 32.0, "rpe": "7–8", "rest": "1м30с"},
        ],
        "legs": [
            {"exercise": "Жим ногами", "sets": 4, "reps": "12–15", "weight": 110.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Болгарские выпады", "sets": 3, "reps": "12–15", "weight": 25.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Румынская тяга", "sets": 3, "reps": "12–15", "weight": 40.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Сгибания ног", "sets": 3, "reps": "12–15", "weight": 35.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Подъём на носки", "sets": 4, "reps": "12–15", "weight": 40.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Пресс", "sets": 3, "reps": "15–20", "weight": 0.0, "rpe": "7", "rest": "1м"},
        ],
        "upper_volume": [
            {"exercise": "Подтягивания обратным хватом с весом", "sets": 3, "reps": "10–12", "weight": 0.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Жим гантелей лёжа", "sets": 4, "reps": "12–15", "weight": 30.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Тяга горизонтального блока", "sets": 3, "reps": "12–15", "weight": 32.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Бицепс (штанга) суперсет", "sets": 3, "reps": "12–15", "weight": 20.0, "rpe": "7–8", "rest": "—"},
            {"exercise": "Трицепс суперсет", "sets": 3, "reps": "12–15", "weight": 15.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Обратная бабочка", "sets": 3, "reps": "15–20", "weight": 12.0, "rpe": "7–8", "rest": "1м30с"},
            {"exercise": "Вис на перекладине", "sets": 3, "reps": "макс. сек.", "weight": 0.0, "rpe": "—", "rest": "1м"},
        ],
    },
    "deload": {
        "upper_strength": [
            {"exercise": "Жим штанги наклонной", "sets": 4, "reps": "10–12", "weight": 30.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Тяга штанги в наклоне", "sets": 3, "reps": "10–12", "weight": 25.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Армейский жим сидя", "sets": 3, "reps": "10–12", "weight": 12.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Подтягивания широкие", "sets": 3, "reps": "8–10", "weight": 0.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Тяга лица", "sets": 3, "reps": "15–20", "weight": 28.0, "rpe": "5–6", "rest": "1м30с"},
        ],
        "legs": [
            {"exercise": "Жим ногами", "sets": 4, "reps": "10–12", "weight": 90.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Болгарские выпады", "sets": 3, "reps": "10–12", "weight": 20.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Румынская тяга", "sets": 3, "reps": "10–12", "weight": 30.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Сгибания ног", "sets": 3, "reps": "10–12", "weight": 30.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Подъём на носки", "sets": 4, "reps": "10–12", "weight": 35.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Пресс", "sets": 3, "reps": "15–20", "weight": 0.0, "rpe": "5", "rest": "1м"},
        ],
        "upper_volume": [
            {"exercise": "Подтягивания обратным хватом", "sets": 3, "reps": "8–10", "weight": 0.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Жим гантелей лёжа", "sets": 4, "reps": "10–12", "weight": 25.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Тяга горизонтального блока", "sets": 3, "reps": "10–12", "weight": 28.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Бицепс (штанга) суперсет", "sets": 3, "reps": "10–12", "weight": 17.5, "rpe": "5–6", "rest": "—"},
            {"exercise": "Трицепс суперсет", "sets": 3, "reps": "10–12", "weight": 12.0, "rpe": "5–6", "rest": "1м30с"},
            {"exercise": "Обратная бабочка", "sets": 3, "reps": "12–15", "weight": 10.0, "rpe": "5–6", "rest": "1м30с"},
        ],
    },
}
