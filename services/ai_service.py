import json
import aiohttp
from groq import AsyncGroq, Groq
from config import GROQ_API_KEY

client = AsyncGroq(api_key=GROQ_API_KEY)
_sync_client = Groq(api_key=GROQ_API_KEY)

MODEL = "llama-3.3-70b-versatile"

# ── Экспертные системные промты ───────────────────────────────────────────────

_COACH_SYSTEM = """Ты элитный тренер по силовым видам спорта с 20-летним опытом работы с профессиональными атлетами. Твоя методология основана на научных исследованиях и практике лучших специалистов мира:

МЕТОДОЛОГИЯ ТРЕНИРОВОК:
- Научная гипертрофия (Brad Schoenfeld, Mike Israetel): механическое напряжение, метаболический стресс, мышечное повреждение
- RPE-тренинг (Mike Tuchscherer / RTS): автоматическая регуляция нагрузки по ощущениям
- Блоковая периодизация: накопление объёма → интенсификация → реализация
- Концепция MEV/MAV/MRV (Renaissance Periodization): минимальный/оптимальный/максимальный объём
- Прогрессивная перегрузка как ключевой принцип роста

ТЕХНИКА УПРАЖНЕНИЙ:
- Биомеханические принципы безопасного и эффективного движения
- Coaching cues от элитных практиков: Boris Sheiko, Ed Coan, Konstantin Konstantinovs
- Концепция "создания напряжения" по всему телу (bracing, leg drive, lat engagement)
- Правила дыхания и стабилизации по методу Valsalva maneuver

КРИТИЧЕСКИЕ БИОМЕХАНИЧЕСКИЕ ПРАВИЛА (никогда не нарушать):
- Жим НАКЛОННОЙ скамье (incline, 30-45°) → штанга касается ВЕРХНЕЙ части груди (у ключицы)
- Жим ГОРИЗОНТАЛЬНОЙ скамье (flat) → штанга касается СЕРЕДИНЫ груди (линия сосков)
- Жим ОБРАТНОГО НАКЛОНА (decline) → штанга касается НИЖНЕЙ части груди
- Жим СТОЯ / СИДЯ (overhead press) → штанга опускается до уровня подбородка/верха груди, не ниже
- Становая тяга: нейтральный позвоночник на всём пути, штанга ведётся вдоль голени
- Приседания: колени следуют за носками, глубина определяется мобильностью бёдер
- Для ЛЮБОГО упражнения: описывай точку касания и траекторию снаряда именно для ЭТОГО варианта, не переноси кью из похожих движений

ПРАКТИКА: Отвечай конкретно, без воды. Только то, что реально работает."""

_NUTRITION_SYSTEM = """Ты спортивный нутрициолог с глубокими знаниями доказательной медицины и спортивной науки. Твоя база знаний:

ПРИНЦИПЫ ПИТАНИЯ:
- Рекомендации ISSN (International Society of Sports Nutrition) по белку: 1.6–2.2 г/кг для гипертрофии
- Энергетический баланс как основа: профицит 200–400 ккал для чистого набора, дефицит 300–500 ккал для похудения
- Тайминг нутриентов: белок каждые 3–5 часов для максимального синтеза (Eric Helms)
- Углеводы как топливо для тренировок: гликоген, инсулиновый отклик
- Жиры: роль в гормональном синтезе (тестостерон, кортизол)
- Гидратация: 35-40 мл/кг массы тела

ДОКАЗАТЕЛЬНАЯ БАЗА: Alan Aragon, Brad Schoenfeld, Eric Helms — "The Muscle and Strength Pyramid"

Отвечай практично: конкретные продукты, граммовки, время приёма."""

_PROGRAM_SYSTEM = _COACH_SYSTEM + "\n\n" + _NUTRITION_SYSTEM + """

ПРИ СОСТАВЛЕНИИ ПРОГРАММ:
- Подбирай упражнения исходя из цели: базовые многосуставные движения приоритет
- Для набора массы: 3-недельный волновой цикл (силовая 4-6 повт → объёмная 8-12 повт → разгрузочная)
- Для похудения: сохраняй силовой тренинг, дефицит создаётся питанием а не кардио
- Для силы: линейная прогрессия + RPE 7-9, низкие повторения, высокие веса
- Для новичков: отрабатывай паттерны движения, не гонись за весами первые 3 месяца
- Отдых между подходами: для силы 3-5 мин, для объёма 1.5-3 мин
- Деload каждые 3-4 недели: снижение объёма на 40-50%, сохранение интенсивности"""


# ── Функции ───────────────────────────────────────────────────────────────────

async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _sync_client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3-turbo",
            language="ru",
        )
    )
    return result.text


async def parse_food(text: str) -> dict:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _NUTRITION_SYSTEM + "\n\nПри анализе еды возвращай ТОЛЬКО JSON без пояснений."},
            {"role": "user", "content": f"""Определи КБЖУ для: "{text}"

Используй точные данные из баз USDA/Роспотребнадзор. Если количество не указано — стандартная порция (200-250г для основных блюд, 30-50г для добавок).

Верни ТОЛЬКО JSON:
{{"calories": число, "protein": число, "carbs": число, "fat": число, "description": "краткое описание блюда"}}"""}
        ],
        max_tokens=200,
        temperature=0.1,
    )
    content = response.choices[0].message.content.strip()
    if "```" in content:
        content = content.split("```")[1].replace("json", "").strip()
    return json.loads(content)


async def analyze_workout(day_type: str, week_type: str, sets_data: list[dict],
                           prev_workout_data: str, user_weight: float) -> str:
    sets_text = "\n".join(
        f"  {s['exercise']}: {s['actual_weight']}кг × {s['reps']} повт., RPE {s['rpe']}"
        for s in sets_data
    )
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _COACH_SYSTEM},
            {"role": "user", "content": f"""Проанализируй тренировку атлета (вес тела: {user_weight}кг).

Тип недели: {week_type} | День: {day_type}

Подходы:
{sets_text}

Предыдущая аналогичная тренировка:
{prev_workout_data or "Первая тренировка такого типа — нет данных для сравнения"}

Дай анализ строго по разделам:

**Итог:** общая оценка тренировки, соответствие плану (1-2 предложения)
**Прогресс:** сравни тоннаж и RPE с прошлой тренировкой — растёт ли нагрузка?
**Замечания:** что было не так — слишком высокий/низкий RPE, отклонения от плана
**На следующую тренировку:** конкретные рекомендации по весам и объёму (числа!)"""}
        ],
        max_tokens=600,
        temperature=0.4,
    )
    return response.choices[0].message.content


async def generate_program(user: dict) -> tuple[list[dict], dict]:
    goal_labels = {
        "mass": "набор мышечной массы (приоритет — гипертрофия, умеренный профицит калорий)",
        "loss": "снижение жировой массы с сохранением мышц (дефицит калорий + силовой тренинг)",
        "strength": "развитие максимальной силы (низкие повторения, высокая интенсивность, RPE 8-9)",
        "tone": "улучшение композиции тела и общей физической формы (умеренный объём, разнообразие)",
    }
    exp_labels = {
        "beginner": "новичок до 1 года — фокус на технике, линейная прогрессия, 1-2 упражнения на группу",
        "intermediate": "средний уровень 1–3 года — волновая периодизация, разнообразие упражнений",
        "advanced": "продвинутый 3+ лет — блоковая периодизация, RPE-управление, вариативность нагрузки",
    }
    equip_labels = {
        "gym": "полный тренажёрный зал (штанга, гантели, все тренажёры)",
        "home": "домашние условия (гантели, турник, петли TRX или резина)",
        "minimal": "без оборудования или минимум (собственный вес, одна пара гантелей)",
    }

    days = user.get('days_per_week', 3)
    split_hint = {
        2: "Full Body × 2 — обе тренировки прорабатывают всё тело",
        3: "Push/Pull/Legs или Upper/Lower/Full — классические трёхдневные сплиты",
        4: "Upper/Lower × 2 — оптимальная частота для гипертрофии",
        5: "Push/Pull/Legs + 2 приоритетных дня (слабые группы)",
        6: "PPL × 2 — высокочастотный тренинг для продвинутых",
    }.get(days, f"{days} разных дней")

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _PROGRAM_SYSTEM + "\nВерни ТОЛЬКО JSON без пояснений."},
            {"role": "user", "content": f"""Составь научно обоснованную программу тренировок и план питания.

ПРОФИЛЬ АТЛЕТА:
- Имя: {user.get('name')}
- Возраст: {user.get('age')} лет
- Вес: {user.get('weight')} кг | Рост: {user.get('height')} см
- Цель: {goal_labels.get(user.get('goal', 'mass'))}
- Опыт: {exp_labels.get(user.get('experience', 'intermediate'))}
- Дней в неделю: {days} ({split_hint})
- Оборудование: {equip_labels.get(user.get('equipment', 'gym'))}
- Травмы/ограничения: {user.get('injuries') or 'нет'}

ТРЕБОВАНИЯ К ПРОГРАММЕ:
1. Применяй подходящую периодизацию для уровня и цели атлета
2. Базовые многосуставные движения — основа программы
3. Веса реалистичные: для новичков лёгкие стартовые, для продвинутых — рабочие
4. RPE-диапазон соответствует типу недели (силовая: RPE 8-9, объёмная: RPE 7-8, разгрузка: RPE 5-6)
5. Исключи упражнения опасные для указанных травм
6. Отдых: для силовых 3-5 мин, для объёмных 60-120 сек

ПИТАНИЕ: рассчитай по формуле Mifflin-St Jeor + коэффициент активности, скорректируй под цель.

Верни ТОЛЬКО JSON:
{{
  "nutrition": {{
    "calories": число,
    "protein": число,
    "carbs": число,
    "fat": число,
    "comment": "обоснование расчёта"
  }},
  "week_types": ["тип_недели_1", "тип_недели_2"],
  "program": [
    {{
      "week_type": "тип_недели",
      "day_type": "тип_дня",
      "order_num": порядковый_номер,
      "exercise": "Название упражнения",
      "sets": число,
      "reps_range": "диапазон повторений",
      "weight": начальный_вес_кг,
      "rpe_range": "диапазон RPE",
      "rest": "время отдыха"
    }}
  ]
}}

Строго {days} разных day_type на каждый week_type."""}
        ],
        max_tokens=4000,
        temperature=0.2,
    )

    content = response.choices[0].message.content.strip()
    if "```" in content:
        content = content.split("```")[1].replace("json", "").strip()

    data = json.loads(content)
    return data["program"], data["nutrition"]


async def get_exercise_technique(exercise: str) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _COACH_SYSTEM},
            {"role": "user", "content": f"""Опиши технику выполнения: «{exercise}»

ВАЖНО: Описывай ТОЛЬКО это конкретное упражнение. Не переносить кью из похожих движений (наклонный жим ≠ горизонтальный: другая точка касания, угол скамьи, акцент на верх груди). Будь биомеханически точен.

Используй биомеханические принципы и coaching cues элитных тренеров. Структура строго такая:

🎯 МЕНТАЛЬНЫЙ ФОКУС
Главные 2 мысли во время подхода — что держать в голове постоянно. Конкретные образы и сигналы именно для этого упражнения.

⚙️ ТЕХНИКА ВЫПОЛНЕНИЯ
1. Стартовая позиция: угол скамьи/оборудование, постановка тела, хват/упор, напряжение до начала движения
2. Фаза опускания (эксцентрик): скорость, контроль, ТОЧНАЯ ТОЧКА КАСАНИЯ (куда именно движется снаряд относительно тела), дыхание
3. Нижняя точка: точное положение снаряда у тела, угол локтей, положение суставов
4. Фаза подъёма (концентрик): траектория движения снаряда, куда толкать/тянуть
5. Дыхание и bracing: когда вдох, когда выдох, давление в животе (Valsalva)

🚫 КРИТИЧЕСКИЕ ОШИБКИ
2-3 ошибки, которые ведут к травме или обнуляют эффект. Объясни ПОЧЕМУ это опасно/неэффективно.

⚠️ ОШИБКИ НОВИЧКА
2-3 типичных косяка в первые месяцы тренировок. Как распознать и исправить.

💪 ПРАВИЛЬНЫЕ ОЩУЩЕНИЯ
Какие мышцы должны гореть и где. Что ты должен чувствовать в каждой фазе — признак правильной техники.

Каждый раздел — 3-5 конкретных строк. Только практика, ноль воды."""}
        ],
        max_tokens=900,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


# Кэш: английское имя упражнения (нижний регистр) → URL картинки
_exercise_index: dict[str, str] | None = None
_index_lock = None  # asyncio.Lock создаётся при первом вызове


async def _build_exercise_index() -> dict[str, str]:
    """Скачивает все упражнения с картинками из wger и строит индекс name→url."""
    index: dict[str, str] = {}
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        # Шаг 1: получаем все главные картинки → {exercise_id: url}
        async with s.get("https://wger.de/api/v2/exerciseimage/?format=json&limit=300&is_main=True") as r:
            img_data = await r.json()
        id_to_url: dict[int, str] = {img["exercise"]: img["image"] for img in img_data.get("results", [])}

        # Шаг 2: пагинируем exerciseinfo, берём английские названия
        url: str | None = "https://wger.de/api/v2/exerciseinfo/?format=json&limit=100"
        while url:
            async with s.get(url) as r:
                page = await r.json()
            for ex in page.get("results", []):
                if ex["id"] not in id_to_url:
                    continue
                en = [t for t in ex.get("translations", []) if t["language"] == 2]
                if en:
                    index[en[0]["name"].lower()] = id_to_url[ex["id"]]
            url = page.get("next")

    return index


async def _get_index() -> dict[str, str]:
    global _exercise_index, _index_lock
    import asyncio
    if _index_lock is None:
        _index_lock = asyncio.Lock()
    async with _index_lock:
        if _exercise_index is None:
            try:
                _exercise_index = await _build_exercise_index()
            except Exception:
                _exercise_index = {}
    return _exercise_index


async def get_exercise_gif(exercise_name: str) -> str | None:
    """Возвращает URL картинки упражнения из wger.de или None."""
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": f"Translate this gym exercise name to English. Reply with ONLY the English name, nothing else: {exercise_name}"}],
            max_tokens=20,
            temperature=0,
        )
        english_name = resp.choices[0].message.content.strip().lower()
    except Exception:
        return None

    try:
        index = await _get_index()
    except Exception:
        return None

    # Точное совпадение
    if english_name in index:
        return index[english_name]

    # Частичное совпадение (поиск подстроки в обе стороны)
    for name, url in index.items():
        if english_name in name or name in english_name:
            return url

    return None


async def get_nutrition_advice(totals: dict, goals: dict) -> str:
    deficit = goals["calories"] - totals["calories"]
    prot_deficit = goals["protein"] - totals["protein"]

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _NUTRITION_SYSTEM},
            {"role": "user", "content": f"""Текущая ситуация по питанию за день:

Цель: {goals['calories']} ккал | Б:{goals['protein']}г | У:{goals['carbs']}г | Ж:{goals['fat']}г
Съедено: {totals['calories']:.0f} ккал | Б:{totals['protein']:.0f}г | У:{totals['carbs']:.0f}г | Ж:{totals['fat']:.0f}г
Осталось: {deficit:.0f} ккал | Белка не хватает: {prot_deficit:.0f}г

Дай практичный совет на оставшуюся часть дня:
- Конкретные продукты и порции чтобы закрыть дефицит
- Приоритет — добрать белок если его не хватает (критично для мышц)
- Если цель выполнена — что можно позволить или как завершить день

Ответ 3-4 строки, конкретно."""}
        ],
        max_tokens=250,
        temperature=0.4,
    )
    return response.choices[0].message.content
