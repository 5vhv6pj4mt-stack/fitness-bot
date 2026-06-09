from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import (get_user, log_food, get_day_nutrition, get_day_food_entries,
                          save_food_template, get_food_templates, get_food_template, delete_food_template,
                          delete_food_entry, get_food_entry)
from keyboards.keyboards import nutrition_menu, main_menu
from services.ai_service import parse_food, parse_food_photo, get_nutrition_advice, transcribe_voice
from handlers.nav import send_nav, track_msg, meal_icon
from states.states import FoodLogging, FoodTemplate

router = Router()


def _tz(utc_offset: int) -> timezone:
    return timezone(timedelta(hours=utc_offset))


def user_today(utc_offset: int = 0) -> str:
    return datetime.now(_tz(utc_offset)).date().isoformat()


def utc_to_local_hhmm(ts: str, utc_offset: int) -> str:
    """SQLite UTC timestamp → HH:MM в часовом поясе пользователя."""
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    return dt.astimezone(_tz(utc_offset)).strftime("%H:%M")


def nutrition_bar(current: float, goal: float, label: str, unit: str = "г") -> str:
    pct = min(current / goal * 100, 100) if goal else 0
    filled = int(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{label}: {bar} {current:.0f}/{goal:.0f}{unit} ({pct:.0f}%)"


@router.message(F.text == "🍽 Питание")
async def nutrition_section(message: Message):
    user = await get_user(message.from_user.id)
    today = user_today(user.get("utc_offset", 0))
    totals = await get_day_nutrition(message.from_user.id, today)
    goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
             "carbs": user["goal_carbs"], "fat": user["goal_fat"]}

    remaining_kcal = goals["calories"] - totals["calories"]
    status = "✅ Цель выполнена!" if remaining_kcal <= 0 else f"До цели: {remaining_kcal:.0f} ккал"

    text = (
        f"🍽 <b>Питание на сегодня</b>\n\n"
        f"{nutrition_bar(totals['calories'], goals['calories'], '🔥 Калории', ' ккал')}\n"
        f"{nutrition_bar(totals['protein'], goals['protein'], '🥩 Белок')}\n"
        f"{nutrition_bar(totals['carbs'], goals['carbs'], '🌾 Углеводы')}\n"
        f"{nutrition_bar(totals['fat'], goals['fat'], '🫒 Жиры')}\n\n"
        f"{status}"
    )
    await send_nav(message, text, reply_markup=nutrition_menu())


@router.message(F.text.in_({"➕ Записать приём пищи", "➕ Записать еду"}))
async def ask_food(message: Message, state: FSMContext):
    await state.set_state(FoodLogging.waiting_input)
    await send_nav(
        message,
        "🍽 Напиши, надиктуй или отправь 📸 <b>фото еды</b>.\n\n"
        "<i>Примеры:</i>\n"
        "• <code>200г куриной грудки, 150г риса, огурец</code>\n"
        "• <code>творог 5% 200г, банан, кофе с молоком</code>\n"
        "• 🎤 голосовое сообщение\n"
        "• 📸 фото тарелки",
        reply_markup=nutrition_menu(),
    )




@router.message(F.text == "🍴 Что съел сегодня")
async def food_detail(message: Message):
    user = await get_user(message.from_user.id)
    utc_offset = user.get("utc_offset", 0)
    today = user_today(utc_offset)
    entries = await get_day_food_entries(message.from_user.id, today)
    totals = await get_day_nutrition(message.from_user.id, today)
    goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
             "carbs": user["goal_carbs"], "fat": user["goal_fat"]}

    entries = [e for e in entries if e["calories"] or e["protein"] or e["carbs"] or e["fat"]]

    if not entries:
        await send_nav(message, "📭 Сегодня ещё ничего не записано.\n\nНажми <b>➕ Записать еду</b>, чтобы добавить приём пищи.", reply_markup=main_menu())
        return

    lines = [f"🍴 <b>Рацион за {today}</b>\n"]
    for i, e in enumerate(entries, 1):
        time = utc_to_local_hhmm(e["created_at"], utc_offset)
        icon = meal_icon(time)
        items = e["description"].split("\n")
        if len(items) > 1:
            items_html = "\n".join(f"   • {it.strip()}" for it in items if it.strip())
            lines.append(
                f"{icon} <b>{i}. Приём пищи</b>  🕐 {time}\n"
                f"{items_html}\n"
                f"   🔥 <b>{e['calories']:.0f} ккал</b>  Б: <b>{e['protein']:.0f}г</b>  У: <b>{e['carbs']:.0f}г</b>  Ж: <b>{e['fat']:.0f}г</b>"
            )
        else:
            lines.append(
                f"{icon} <b>{i}. {e['description']}</b>\n"
                f"   🕐 {time}  ·  🔥 <b>{e['calories']:.0f} ккал</b>\n"
                f"   Б: <b>{e['protein']:.0f}г</b>  У: <b>{e['carbs']:.0f}г</b>  Ж: <b>{e['fat']:.0f}г</b>"
            )

    remaining = goals["calories"] - totals["calories"]
    cal_status = "✅ Цель выполнена!" if remaining <= 0 else f"ещё {remaining:.0f} ккал"

    prot_pct = min(totals['protein'] / goals['protein'] * 100, 100) if goals['protein'] else 0
    carb_pct = min(totals['carbs'] / goals['carbs'] * 100, 100) if goals['carbs'] else 0
    fat_pct = min(totals['fat'] / goals['fat'] * 100, 100) if goals['fat'] else 0

    lines.append(
        f"\n{'─' * 22}\n"
        f"📊 <b>Итого за день ({len(entries)} приём{'а' if 2 <= len(entries) <= 4 else 'ов' if len(entries) >= 5 else ''}):</b>\n"
        f"🔥 <b>{totals['calories']:.0f}</b> / {goals['calories']} ккал — {cal_status}\n"
        f"🥩 Белок:    <b>{totals['protein']:.0f}</b> / {goals['protein']}г ({prot_pct:.0f}%)\n"
        f"🌾 Углеводы: <b>{totals['carbs']:.0f}</b> / {goals['carbs']}г ({carb_pct:.0f}%)\n"
        f"🫒 Жиры:     <b>{totals['fat']:.0f}</b> / {goals['fat']}г ({fat_pct:.0f}%)"
    )

    del_buttons = [
        InlineKeyboardButton(text=f"🗑 {i}", callback_data=f"food_del:{e['id']}")
        for i, e in enumerate(entries, 1)
    ]
    del_rows = [del_buttons[i:i+4] for i in range(0, len(del_buttons), 4)]
    del_kb = InlineKeyboardMarkup(inline_keyboard=del_rows)
    await send_nav(message, "\n".join(lines), reply_markup=main_menu())
    await message.answer("Удалить приём пищи:", reply_markup=del_kb)



@router.message(F.text == "💡 Совет по питанию")
async def nutrition_tip(message: Message):
    user = await get_user(message.from_user.id)
    totals = await get_day_nutrition(message.from_user.id, user_today(user.get("utc_offset", 0)))
    goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
             "carbs": user["goal_carbs"], "fat": user["goal_fat"]}

    msg_id = await send_nav(message, "⏳ Анализирую питание...", reply_markup=nutrition_menu())
    advice = await get_nutrition_advice(totals, goals)
    try:
        await message.bot.edit_message_text(
            f"💡 {advice}", chat_id=message.chat.id, message_id=msg_id, parse_mode="HTML"
        )
    except Exception:
        await message.answer(f"💡 {advice}")


async def _process_food(message: Message, state: FSMContext, food_text: str,
                        status_msg=None, prefetched_result: dict = None):
    """Общая логика: парсим текст/фото еды и сохраняем."""
    await state.clear()  # сразу блокируем повторный ввод
    user = await get_user(message.from_user.id)
    utc_offset = user.get("utc_offset", 0)

    if status_msg is None:
        status_msg = await message.answer("⏳ Считаю КБЖУ...")

    try:
        result = prefetched_result if prefetched_result is not None else await parse_food(food_text)

        if not result.get("calories") and not result.get("protein") and not result.get("carbs") and not result.get("fat"):
            await status_msg.edit_text(
                "❌ Не удалось определить КБЖУ. Попробуй написать подробнее, например:\n"
                "<code>200г куриной грудки, 150г риса</code>",
                parse_mode="HTML"
            )
            track_msg(message.from_user.id, status_msg.message_id)
            return

        desc = result.get("description", food_text[:300])
        entry_id = await log_food(
            message.from_user.id, user_today(utc_offset),
            desc, result["calories"], result["protein"], result["carbs"], result["fat"]
        )

        totals = await get_day_nutrition(message.from_user.id, user_today(utc_offset))
        goals = {"calories": user["goal_calories"], "protein": user["goal_protein"],
                 "carbs": user["goal_carbs"], "fat": user["goal_fat"]}
        remaining = goals["calories"] - totals["calories"]

        items = desc.split("\n")
        if len(items) > 1:
            items_html = "\n".join(f"  • {it.strip()}" for it in items if it.strip())
            recorded_block = f"✅ <b>Записано:</b>\n{items_html}"
        else:
            recorded_block = f"✅ <b>Записано:</b> {desc}"
        await status_msg.edit_text(
            f"{recorded_block}\n\n"
            f"🔥 {result['calories']:.0f} ккал · "
            f"Б: {result['protein']:.0f}г · "
            f"У: {result['carbs']:.0f}г · "
            f"Ж: {result['fat']:.0f}г\n\n"
            f"<b>За день итого:</b> {totals['calories']:.0f} / {goals['calories']} ккал\n"
            f"{'✅ Цель выполнена!' if remaining <= 0 else f'До цели: {remaining:.0f} ккал'}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💾 Шаблон", callback_data=f"tmpl_save:{entry_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"food_del:{entry_id}"),
            ]])
        )
        track_msg(message.from_user.id, status_msg.message_id)

    except Exception as e:
        await state.set_state(FoodLogging.waiting_input)  # восстанавливаем — можно попробовать снова
        await status_msg.edit_text(f"❌ Не удалось распознать. Попробуй написать подробнее.\n<i>{e}</i>", parse_mode="HTML")
        track_msg(message.from_user.id, status_msg.message_id)


_NAV_BUTTONS = {
    "🏠 Главное меню", "💪 Тренировка", "🍽 Питание", "📊 Статистика", "⚙️ Настройки",
    "➕ Записать приём пищи", "➕ Записать еду", "💡 Совет по питанию",
    "🍴 Что съел сегодня", "📌 Шаблоны",
}


@router.message(
    FoodLogging.waiting_input,
    F.text,
    ~F.text.in_(_NAV_BUTTONS),
    ~F.text.startswith("/"),
    ~F.text.startswith("▶️"),
)
async def handle_food_text(message: Message, state: FSMContext):
    await _process_food(message, state, message.text)


@router.message(FoodLogging.waiting_input, F.voice)
async def handle_food_voice(message: Message, state: FSMContext):
    msg = await message.answer("🎤 Распознаю голос...")
    try:
        file = await message.bot.get_file(message.voice.file_id)
        audio_bytes = await message.bot.download_file(file.file_path)
        text = await transcribe_voice(audio_bytes.read(), "voice.ogg")
        await msg.edit_text(f"🎤 Распознано: <i>{text}</i>\n\n⏳ Считаю КБЖУ...", parse_mode="HTML")
        await _process_food(message, state, text, status_msg=msg)
    except Exception as e:
        await msg.edit_text(f"❌ Не удалось распознать голос: {e}")


async def _process_food_photo(message: Message, state: FSMContext):
    """Общая логика для анализа фото еды."""
    msg = await message.answer("📸 Анализирую фото...")
    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        img_bytes = await message.bot.download_file(file.file_path)
        result = await parse_food_photo(img_bytes.read())

        if not result.get("calories") and not result.get("protein") and not result.get("carbs") and not result.get("fat"):
            await msg.edit_text(
                "❌ Не удалось определить КБЖУ по фото. Попробуй сфотографировать ближе или опиши еду текстом.",
                parse_mode="HTML"
            )
            return

        food_text = result.get("description", "Фото еды")
        await _process_food(message, state, food_text, status_msg=msg, prefetched_result=result)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка анализа фото: {e}")


@router.message(FoodLogging.waiting_input, F.photo)
async def handle_food_photo_in_state(message: Message, state: FSMContext):
    await _process_food_photo(message, state)


@router.message(F.photo)
async def handle_food_photo_direct(message: Message, state: FSMContext):
    """Фото вне FSM — сразу анализируем как еду."""
    await _process_food_photo(message, state)


@router.callback_query(F.data == "log_food")
async def cb_log_food(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FoodLogging.waiting_input)
    await callback.message.answer(
        "🍽 Напиши, надиктуй или отправь 📸 <b>фото еды</b>.\n\n"
        "<i>Примеры:</i>\n"
        "• <code>200г куриной грудки, 150г риса, огурец</code>\n"
        "• 🎤 голосовое сообщение\n"
        "• 📸 фото тарелки",
        parse_mode="HTML",
    )
    await callback.answer()


# ── Шаблоны питания ────────────────────────────────────────────────────────────

def _templates_kb(templates: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for t in templates:
        rows.append([InlineKeyboardButton(
            text=f"{t['name']} — {t['calories']:.0f} ккал",
            callback_data=f"tmpl_detail:{t['id']}"
        )])
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="tmpl_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _template_detail_kb(template_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Записать сейчас", callback_data=f"tmpl_log:{template_id}")],
        [InlineKeyboardButton(text="🗑 Удалить шаблон", callback_data=f"tmpl_delete:{template_id}")],
        [InlineKeyboardButton(text="← Назад", callback_data="tmpl_list")],
    ])


@router.message(F.text == "📌 Шаблоны")
async def show_templates(message: Message):
    templates = await get_food_templates(message.from_user.id)
    if not templates:
        await send_nav(
            message,
            "📌 <b>Шаблоны питания</b>\n\nШаблонов пока нет.\n\n"
            "После записи еды нажми <b>💾 Сохранить как шаблон</b> — "
            "и сможешь добавлять её одним нажатием.",
            reply_markup=nutrition_menu(),
        )
        return
    await send_nav(message, "📌 <b>Шаблоны питания</b>\n\nВыбери что записать:", reply_markup=nutrition_menu())
    sent = await message.answer("👇", reply_markup=_templates_kb(templates))
    track_msg(message.from_user.id, sent.message_id)


@router.callback_query(F.data == "tmpl_list")
async def cb_tmpl_list(callback: CallbackQuery):
    templates = await get_food_templates(callback.from_user.id)
    if not templates:
        await callback.message.edit_text("📌 Шаблонов пока нет.", reply_markup=None)
        await callback.answer()
        return
    await callback.message.edit_text("📌 <b>Шаблоны питания</b>\n\nВыбери что записать:",
                                      reply_markup=_templates_kb(templates), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "tmpl_close")
async def cb_tmpl_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data.startswith("tmpl_detail:"))
async def cb_tmpl_detail(callback: CallbackQuery):
    template_id = int(callback.data.split(":", 1)[1])
    t = await get_food_template(template_id, callback.from_user.id)
    if not t:
        await callback.answer("Шаблон не найден")
        return
    items = (t["description"] or "").split("\n")
    if len(items) > 1:
        desc_html = "\n".join(f"  • {it.strip()}" for it in items if it.strip())
    else:
        desc_html = t["description"] or t["name"]
    await callback.message.edit_text(
        f"📌 <b>{t['name']}</b>\n\n{desc_html}\n\n"
        f"🔥 {t['calories']:.0f} ккал · Б: {t['protein']:.0f}г · У: {t['carbs']:.0f}г · Ж: {t['fat']:.0f}г",
        reply_markup=_template_detail_kb(template_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tmpl_log:"))
async def cb_tmpl_log(callback: CallbackQuery):
    template_id = int(callback.data.split(":", 1)[1])
    t = await get_food_template(template_id, callback.from_user.id)
    if not t:
        await callback.answer("Шаблон не найден")
        return
    user = await get_user(callback.from_user.id)
    utc_offset = user.get("utc_offset", 0)
    await log_food(callback.from_user.id, user_today(utc_offset),
                   t["description"] or t["name"], t["calories"], t["protein"], t["carbs"], t["fat"])
    totals = await get_day_nutrition(callback.from_user.id, user_today(utc_offset))
    remaining = user["goal_calories"] - totals["calories"]
    await callback.message.edit_text(
        f"✅ <b>{t['name']}</b> записан!\n\n"
        f"🔥 {t['calories']:.0f} ккал · Б: {t['protein']:.0f}г · У: {t['carbs']:.0f}г · Ж: {t['fat']:.0f}г\n\n"
        f"<b>За день итого:</b> {totals['calories']:.0f} / {user['goal_calories']} ккал\n"
        f"{'✅ Цель выполнена!' if remaining <= 0 else f'До цели: {remaining:.0f} ккал'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="← К шаблонам", callback_data="tmpl_list")
        ]]),
        parse_mode="HTML",
    )
    await callback.answer("✅ Записано!")


@router.callback_query(F.data.startswith("tmpl_delete:"))
async def cb_tmpl_delete(callback: CallbackQuery):
    template_id = int(callback.data.split(":", 1)[1])
    await delete_food_template(template_id, callback.from_user.id)
    templates = await get_food_templates(callback.from_user.id)
    if not templates:
        await callback.message.edit_text("🗑 Шаблон удалён. Шаблонов больше нет.", reply_markup=None)
    else:
        await callback.message.edit_text("🗑 Шаблон удалён.\n\n📌 <b>Шаблоны питания:</b>",
                                          reply_markup=_templates_kb(templates), parse_mode="HTML")
    await callback.answer("Удалено")


@router.callback_query(F.data.startswith("tmpl_save:"))
async def cb_tmpl_save(callback: CallbackQuery, state: FSMContext):
    entry_id = int(callback.data.split(":", 1)[1])
    from database.db import get_food_entry
    entry = await get_food_entry(entry_id)
    if not entry:
        await callback.answer("Запись не найдена")
        return
    await state.set_state(FoodTemplate.waiting_name)
    await state.update_data(tmpl_entry_id=entry_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "💾 Как назвать шаблон?\nНапример: <code>Мой завтрак</code> или <code>Обед стандарт</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(FoodTemplate.waiting_name)
async def tmpl_name_input(message: Message, state: FSMContext):
    name = message.text.strip()[:50]
    data = await state.get_data()
    entry_id = data.get("tmpl_entry_id")
    await state.clear()
    from database.db import get_food_entry
    entry = await get_food_entry(entry_id)
    if not entry:
        await message.answer("❌ Не удалось найти запись.")
        return
    await save_food_template(message.from_user.id, name,
                              entry["description"], entry["calories"],
                              entry["protein"], entry["carbs"], entry["fat"])
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(
        f"✅ Шаблон <b>{name}</b> сохранён!\n"
        f"Теперь доступен в <b>📌 Шаблоны</b>.",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("food_del:"))
async def cb_food_delete(callback: CallbackQuery):
    entry_id = int(callback.data.split(":", 1)[1])
    entry = await get_food_entry(entry_id)
    if not entry or entry["user_id"] != callback.from_user.id:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    await delete_food_entry(entry_id)
    short = entry["description"][:40] + ("…" if len(entry["description"]) > 40 else "")
    await callback.answer(f"Удалено: {short}", show_alert=False)
    try:
        await callback.message.delete()
    except Exception:
        pass
