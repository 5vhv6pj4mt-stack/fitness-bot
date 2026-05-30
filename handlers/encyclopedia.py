import asyncio
import html as html_module
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.ai_service import get_exercise_technique, get_exercise_gif

router = Router()

# Каталог упражнений: категория → [(рус. название, англ. название)]
CATALOG: dict[str, list[tuple[str, str]]] = {
    "🏋️ Грудь": [
        ("Жим штанги лёжа", "Bench Press"),
        ("Жим гантелей лёжа", "Dumbbell Bench Press"),
        ("Жим на наклонной скамье", "Incline Bench Press"),
        ("Разводка гантелей", "Dumbbell Flyes"),
        ("Кроссовер на блоке", "Cable Crossover"),
        ("Отжимания на брусьях", "Dips"),
    ],
    "🔙 Спина": [
        ("Подтягивания", "Pull-ups"),
        ("Тяга штанги в наклоне", "Barbell Row"),
        ("Тяга верхнего блока", "Lat Pulldown"),
        ("Тяга горизонтального блока", "Seated Cable Row"),
        ("Становая тяга", "Deadlift"),
        ("Тяга гантели одной рукой", "One-Arm Dumbbell Row"),
    ],
    "🦵 Ноги": [
        ("Приседания со штангой", "Barbell Squat"),
        ("Жим ногами", "Leg Press"),
        ("Выпады", "Lunges"),
        ("Разгибания ног", "Leg Extensions"),
        ("Сгибания ног лёжа", "Lying Leg Curl"),
        ("Подъём на носки стоя", "Standing Calf Raise"),
    ],
    "💪 Плечи": [
        ("Жим штанги стоя", "Overhead Press"),
        ("Жим гантелей сидя", "Dumbbell Shoulder Press"),
        ("Махи гантелями в стороны", "Lateral Raises"),
        ("Тяга штанги к подбородку", "Upright Row"),
        ("Махи в наклоне (задний пучок)", "Rear Delt Flyes"),
    ],
    "💪 Руки": [
        ("Подъём штанги на бицепс", "Barbell Curl"),
        ("Молотковые сгибания", "Hammer Curl"),
        ("Французский жим", "Skull Crushers"),
        ("Разгибания на блоке", "Tricep Pushdown"),
        ("Жим узким хватом", "Close-Grip Bench Press"),
        ("Сгибания на блоке", "Cable Curl"),
    ],
    "🎯 Пресс и кор": [
        ("Скручивания", "Crunches"),
        ("Подъём ног в висе", "Hanging Leg Raises"),
        ("Планка", "Plank"),
        ("Велосипед", "Bicycle Crunch"),
        ("Гиперэкстензия", "Hyperextensions"),
    ],
}

CATEGORIES = list(CATALOG.keys())

# Кэш техники: (рус. название) → текст
_technique_cache: dict[str, str] = {}


def _categories_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(CATEGORIES), 2):
        row = [InlineKeyboardButton(text=CATEGORIES[i], callback_data=f"ec:{i}")]
        if i + 1 < len(CATEGORIES):
            row.append(InlineKeyboardButton(text=CATEGORIES[i + 1], callback_data=f"ec:{i+1}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _exercises_kb(cat_idx: int) -> InlineKeyboardMarkup:
    cat = CATEGORIES[cat_idx]
    exercises = CATALOG[cat]
    rows = [[InlineKeyboardButton(text=name, callback_data=f"ee:{cat_idx}:{i}")]
            for i, (name, _) in enumerate(exercises)]
    rows.append([InlineKeyboardButton(text="← Назад к категориям", callback_data="enc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_to_cat_kb(cat_idx: int) -> InlineKeyboardMarkup:
    cat = CATEGORIES[cat_idx]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"← Назад: {cat}", callback_data=f"ec:{cat_idx}")],
        [InlineKeyboardButton(text="↩️ К категориям", callback_data="enc")],
    ])


@router.message(F.text == "📚 Энциклопедия")
async def encyclopedia_start(message: Message):
    await message.answer(
        "📚 <b>Энциклопедия упражнений</b>\n\nВыбери группу мышц:",
        reply_markup=_categories_kb(),
    )


@router.callback_query(F.data == "enc")
async def cb_categories(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 <b>Энциклопедия упражнений</b>\n\nВыбери группу мышц:",
        reply_markup=_categories_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ec:"))
async def cb_category(callback: CallbackQuery):
    cat_idx = int(callback.data.split(":")[1])
    cat = CATEGORIES[cat_idx]
    exercises = CATALOG[cat]
    await callback.message.edit_text(
        f"📚 <b>{cat}</b>\n\nВыбери упражнение:",
        reply_markup=_exercises_kb(cat_idx),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ee:"))
async def cb_exercise(callback: CallbackQuery):
    _, cat_idx_s, ex_idx_s = callback.data.split(":")
    cat_idx, ex_idx = int(cat_idx_s), int(ex_idx_s)
    cat = CATEGORIES[cat_idx]
    ru_name, en_name = CATALOG[cat][ex_idx]

    await callback.answer()
    await callback.message.edit_text(f"⏳ Загружаю технику <b>{ru_name}</b>...", reply_markup=None)

    try:
        if ru_name in _technique_cache:
            technique = _technique_cache[ru_name]
            gif_url = await get_exercise_gif(en_name)
        else:
            technique, gif_url = await asyncio.gather(
                get_exercise_technique(ru_name),
                get_exercise_gif(en_name),
                return_exceptions=True,
            )
            if isinstance(technique, Exception):
                raise technique
            _technique_cache[ru_name] = technique

        back_kb = _back_to_cat_kb(cat_idx)

        # Отправляем картинку отдельным сообщением если нашлась
        if isinstance(gif_url, str) and gif_url:
            try:
                if gif_url.lower().endswith(".gif"):
                    await callback.message.answer_animation(gif_url)
                else:
                    await callback.message.answer_photo(gif_url)
            except Exception:
                pass

        await callback.message.edit_text(
            f"📖 <b>{html_module.escape(ru_name)}</b>\n\n{html_module.escape(technique)}",
            reply_markup=back_kb,
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Не удалось загрузить технику: {e}",
            reply_markup=_back_to_cat_kb(cat_idx),
        )
