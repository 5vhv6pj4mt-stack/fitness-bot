from aiogram.types import Message

# user_id → список message_id бота, которые нужно удалить при следующей навигации
_last_nav: dict[int, list[int]] = {}


def meal_icon(time_str: str) -> str:
    hour = int(time_str[:2])
    if hour < 10:
        return "🌅"
    if hour < 13:
        return "☀️"
    if hour < 17:
        return "🌤"
    if hour < 21:
        return "🌆"
    return "🌙"


async def send_nav(message: Message, text: str, reply_markup=None, parse_mode: str = "HTML") -> int:
    user_id = message.from_user.id

    # Удаляем сообщение пользователя (нажатие кнопки)
    try:
        await message.delete()
    except Exception:
        pass

    # Удаляем все предыдущие отслеживаемые сообщения бота
    for prev_id in _last_nav.pop(user_id, []):
        try:
            await message.bot.delete_message(message.chat.id, prev_id)
        except Exception:
            pass

    sent = await message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
    _last_nav[user_id] = [sent.message_id]
    return sent.message_id


def track_msg(user_id: int, message_id: int):
    """Добавляет message_id в список отслеживаемых — удалится при следующей навигации."""
    _last_nav.setdefault(user_id, []).append(message_id)


def clear_nav(user_id: int):
    _last_nav.pop(user_id, None)
