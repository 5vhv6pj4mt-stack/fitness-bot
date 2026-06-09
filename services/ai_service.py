import asyncio
import json
import aiohttp
from groq import Groq
from anthropic import AsyncAnthropic
from config import GROQ_API_KEY, ANTHROPIC_API_KEY

# Groq только для транскрипции голоса (Whisper)
_groq_sync = Groq(api_key=GROQ_API_KEY)

# Claude для всего остального
_claude = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-6"

# ── Системные промты ───────────────────────────────────────────────────────────

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
- Deload каждые 3-4 недели: снижение объёма на 40-50%, сохранение интенсивности"""


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _fix_json_strings(s: str) -> str:
    result = []
    in_string = False
    escaped = False
    for ch in s:
        if escaped:
            result.append(ch)
            escaped = False
        elif ch == '\\' and in_string:
            result.append(ch)
            escaped = True
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string and ch == '\n':
            result.append('\\n')
        elif in_string and ch == '\r':
            result.append('\\r')
        elif in_string and ch == '\t':
            result.append('\\t')
        else:
            result.append(ch)
    return ''.join(result)


def _extract_json(content: str) -> dict:
    if "```" in content:
        content = content.split("```")[1].replace("json", "").strip()
    content = _fix_json_strings(content)
    data = json.loads(content)
    for key in ("calories", "protein", "carbs", "fat"):
        if key in data:
            data[key] = float(str(data[key]).replace(",", ".").split()[0])
    return data


async def _ask(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.3) -> str:
    try:
        response = await asyncio.wait_for(
            _claude.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ),
            timeout=30.0,
        )
        return response.content[0].text
    except asyncio.TimeoutError:
        raise RuntimeError("AI не отвечает, попробуй ещё раз")
    except Exception as e:
        raise RuntimeError(f"Ошибка AI: {e}") from e


# ── Публичные функции ─────────────────────────────────────────────────────────

async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _groq_sync.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3-turbo",
            language="ru",
        )
    )
    return result.text


_PARSE_FOOD_PROMPT = """\
Определи суммарное КБЖУ для всей еды: "{text}"

Правила:
- Игнорируй любые числа КБЖУ, если они уже указаны в тексте — считай сам по ингредиентам
- Если количество не указано — стандартная порция (200-250г для блюд, 30-50г для добавок)
- Используй данные USDA/Роспотребнадзор
- В поле description перечисли КАЖДЫЙ продукт отдельной строкой через \\n, формат: "Название количество — X ккал"
  Пример: "Рис бурый 200г — 220 ккал\\nКурица со сметаной 200г — 330 ккал\\nМасло льняное 8мл — 70 ккал"
- Не объединяй продукты в одну строку

Верни ТОЛЬКО JSON. Все 4 числовых поля — итоговые целые числа, БЕЗ арифметических выражений:
{{"calories": 620, "protein": 58, "carbs": 46, "fat": 18, "description": "Продукт 1 200г — 300 ккал\\nПродукт 2 150г — 320 ккал"}}"""

_PARSE_PHOTO_PROMPT = """\
Посмотри на фото еды. Определи все продукты, оцени порции и рассчитай суммарное КБЖУ.

Правила:
- Если вес неясен — используй стандартные порции (200-250г для основных блюд)
- В description перечисли КАЖДЫЙ продукт с новой строки: "Название ~вес — X ккал"
- Используй данные USDA/Роспотребнадзор

Верни ТОЛЬКО JSON (без markdown, без пояснений):
{"calories": 620, "protein": 45, "carbs": 60, "fat": 18, "description": "Рис 200г — 220 ккал\\nКурица 150г — 250 ккал\\nОгурец — 15 ккал"}"""


async def parse_food(text: str) -> dict:
    system = "Ты нутрициолог. Считаешь КБЖУ. Возвращаешь ТОЛЬКО валидный JSON с числовыми значениями — никаких арифметических выражений, только готовые числа."
    try:
        content = await _ask(system, _PARSE_FOOD_PROMPT.format(text=text), max_tokens=300, temperature=0.1)
        return _extract_json(content.strip())
    except Exception:
        import re
        clean = re.sub(r'[~≈]?\d+[\.,]?\d*\s*(г|гр|ккал|кг|мл|л)?', '', text)
        clean = re.sub(r'[-–—•*]\s*', '', clean).strip() or text
        content = await _ask(
            "Ты нутрициолог. Возвращаешь ТОЛЬКО JSON с числовыми значениями КБЖУ.",
            _PARSE_FOOD_PROMPT.format(text=clean),
            max_tokens=300, temperature=0.1,
        )
        return _extract_json(content.strip())


async def parse_food_photo(image_bytes: bytes) -> dict:
    import base64
    b64 = base64.b64encode(image_bytes).decode()
    response = await _claude.messages.create(
        model=MODEL,
        max_tokens=400,
        system="Ты нутрициолог. Считаешь КБЖУ. Возвращаешь ТОЛЬКО валидный JSON с числовыми значениями — никаких арифметических выражений, только готовые числа.",
        temperature=0.1,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                },
                {"type": "text", "text": _PARSE_PHOTO_PROMPT},
            ],
        }],
    )
    return _extract_json(response.content[0].text.strip())


async def analyze_workout(day_type: str, week_type: str, sets_data: list[dict],
                           prev_workout_data: str, user_weight: float) -> str:
    sets_text = "\n".join(
        f"  {s['exercise']}: {s['actual_weight']}кг × {s['reps']} повт., RPE {s['rpe']}"
        for s in sets_data
    )
    return await _ask(
        _COACH_SYSTEM,
        f"""Проанализируй тренировку атлета (вес тела: {user_weight}кг).

Тип недели: {week_type} | День: {day_type}

Подходы:
{sets_text}

Предыдущая аналогичная тренировка:
{prev_workout_data or "Первая тренировка такого типа — нет данных для сравнения"}

Дай анализ строго по разделам:

**Итог:** общая оценка тренировки, соответствие плану (1-2 предложения)
**Прогресс:** сравни тоннаж и RPE с прошлой тренировкой — растёт ли нагрузка?
**Замечания:** что было не так — слишком высокий/низкий RPE, отклонения от плана
**На следующую тренировку:** конкретные рекомендации по весам и объёму (числа!)""",
        max_tokens=600, temperature=0.4,
    )


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

    content = await _ask(
        _PROGRAM_SYSTEM + "\nВерни ТОЛЬКО JSON без пояснений.",
        f"""Составь научно обоснованную программу тренировок и план питания.

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

Строго {days} разных day_type на каждый week_type.""",
        max_tokens=4000, temperature=0.2,
    )

    if "```" in content:
        content = content.split("```")[1].replace("json", "").strip()
    data = json.loads(content)
    return data["program"], data["nutrition"]


async def get_exercise_technique(exercise: str) -> str:
    return await _ask(
        _COACH_SYSTEM,
        f"""Опиши технику выполнения: «{exercise}»

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

Каждый раздел — 3-5 конкретных строк. Только практика, ноль воды.""",
        max_tokens=900, temperature=0.2,
    )


async def get_exercise_gif(exercise_name: str) -> str | None:
    from config import RAPIDAPI_KEY
    try:
        english_name = (await _ask(
            "",
            f"Translate this gym exercise name to English. Reply with ONLY the English name, nothing else: {exercise_name}",
            max_tokens=20, temperature=0,
        )).strip()
    except Exception:
        english_name = exercise_name

    if RAPIDAPI_KEY:
        result = await _get_gif_exercisedb(english_name)
        if result:
            return result

    # fallback — wger статичные изображения
    try:
        index = await _get_index()
        key = english_name.lower()
        if key in index:
            return index[key]
        for name, url in index.items():
            if key in name or name in key:
                return url
    except Exception:
        pass
    return None


async def get_nutrition_advice(totals: dict, goals: dict) -> str:
    deficit = goals["calories"] - totals["calories"]
    prot_deficit = goals["protein"] - totals["protein"]
    return await _ask(
        _NUTRITION_SYSTEM,
        f"""Текущая ситуация по питанию за день:

Цель: {goals['calories']} ккал | Б:{goals['protein']}г | У:{goals['carbs']}г | Ж:{goals['fat']}г
Съедено: {totals['calories']:.0f} ккал | Б:{totals['protein']:.0f}г | У:{totals['carbs']:.0f}г | Ж:{totals['fat']:.0f}г
Осталось: {deficit:.0f} ккал | Белка не хватает: {prot_deficit:.0f}г

Дай практичный совет на оставшуюся часть дня:
- Конкретные продукты и порции чтобы закрыть дефицит
- Приоритет — добрать белок если его не хватает (критично для мышц)
- Если цель выполнена — что можно позволить или как завершить день

Ответ 3-4 строки, конкретно.""",
        max_tokens=250, temperature=0.4,
    )


# ── ExerciseDB (RapidAPI) — анимированные GIF ────────────────────────────────

_gif_cache: dict[str, str | None] = {}  # in-memory кэш на сессию
_GIF_CACHE_FILE = "exercise_gif_cache.json"


def _load_gif_cache() -> None:
    import json, os
    global _gif_cache
    if os.path.exists(_GIF_CACHE_FILE):
        try:
            with open(_GIF_CACHE_FILE) as f:
                _gif_cache = json.load(f)
        except Exception:
            _gif_cache = {}


def _save_gif_cache() -> None:
    import json
    try:
        with open(_GIF_CACHE_FILE, "w") as f:
            json.dump(_gif_cache, f)
    except Exception:
        pass


_load_gif_cache()


async def _get_gif_exercisedb(english_name: str) -> str | None:
    from config import RAPIDAPI_KEY
    key = english_name.lower().strip()

    if key in _gif_cache:
        return _gif_cache[key]

    try:
        encoded = key.replace(" ", "%20")
        url = f"https://exercisedb.p.rapidapi.com/exercises/name/{encoded}?limit=5&offset=0"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "exercisedb.p.rapidapi.com",
        }
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url, headers=headers) as r:
                if r.status != 200:
                    return None
                data = await r.json()

        gif_url = data[0]["gifUrl"] if data else None
        _gif_cache[key] = gif_url
        _save_gif_cache()
        return gif_url
    except Exception:
        return None


# ── Кэш wger (fallback, статичные изображения) ───────────────────────────────

_exercise_index: dict[str, str] | None = None
_index_lock = None


async def _build_exercise_index() -> dict[str, str]:
    index: dict[str, str] = {}
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.get("https://wger.de/api/v2/exerciseimage/?format=json&limit=300&is_main=True") as r:
            img_data = await r.json()
        id_to_url: dict[int, str] = {img["exercise"]: img["image"] for img in img_data.get("results", [])}

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
