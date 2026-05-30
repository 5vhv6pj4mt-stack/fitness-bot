"""Утилиты для чистой навигации: удаляем сообщения пользователя и заменяем предыдущее навигационное сообщение бота."""
from aiogram.types import Message

# user_id → последнее навигационное сообщение бота
_last_nav: dict[int, int] = {}


async def send_nav(message: Message, text: str, reply_markup=None, parse_mode: str = "HTML") -> int:
    """Удаляет тап пользователя, отправляет новое сообщение.
    Предыдущее nav-сообщение удаляется только при переходе с клавиатурой —
    иначе reply keyboard пропадает у пользователя."""
    user_id = message.from_user.id

    # Удаляем сообщение пользователя (нажатие кнопки)
    try:
        await message.delete()
    except Exception:
        pass

    # Удаляем предыдущее nav-сообщение только если отправляем новую клавиатуру
    if reply_markup is not None:
        prev_id = _last_nav.get(user_id)
        if prev_id:
            try:
                await message.bot.delete_message(message.chat.id, prev_id)
            except Exception:
                pass

    sent = await message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
    _last_nav[user_id] = sent.message_id
    return sent.message_id


def clear_nav(user_id: int):
    """Очищает трекинг после завершения навигации (например начало тренировки)."""
    _last_nav.pop(user_id, None)
