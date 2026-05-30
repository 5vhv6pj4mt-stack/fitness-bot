"""Планировщик напоминаний о приёмах пищи."""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None
_bot: Bot = None


async def _send_meal_reminder(user_id: int):
    if _bot is None:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ Записать", callback_data="log_food")
    ]])
    try:
        await _bot.send_message(
            user_id,
            "🍽 <b>Пора перекусить?</b>\nЗапиши следующий приём пищи, пока не забыл!",
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception as e:
        logger.warning("Не удалось отправить напоминание %s: %s", user_id, e)


def schedule_next_meal_reminder(user_id: int, delay_minutes: int = 120):
    """Ставит разовое напоминание через delay_minutes минут. Перезаписывает предыдущее."""
    if _scheduler is None:
        return
    job_id = f"meal_{user_id}"
    run_at = datetime.now() + timedelta(minutes=delay_minutes)
    _scheduler.add_job(
        _send_meal_reminder,
        "date",
        run_date=run_at,
        args=[user_id],
        id=job_id,
        replace_existing=True,
    )
    logger.info("Напоминание для %s через %d мин", user_id, delay_minutes)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    global _scheduler, _bot
    _bot = bot
    _scheduler = AsyncIOScheduler(timezone="Asia/Krasnoyarsk")
    return _scheduler
