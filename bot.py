import asyncio
import logging
import os
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from config import BOT_TOKEN
from database.db import init_db, get_all_onboarded_users, get_meal_reminders, get_user
from handlers import main_menu, nutrition, workout, onboarding, settings, stats, edit, test_video
from services.scheduler import setup_scheduler, setup_daily_reminders, setup_workout_reminder, setup_morning_brief

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log")]
)
logger = logging.getLogger(__name__)

PID_FILE = "bot.pid"


def _kill_previous():
    if not os.path.exists(PID_FILE):
        return
    try:
        with open(PID_FILE) as f:
            old_pid = int(f.read().strip())
        if old_pid != os.getpid():
            os.kill(old_pid, signal.SIGTERM)
            logger.info("Остановлен старый процесс PID=%s", old_pid)
    except (ValueError, ProcessLookupError, PermissionError):
        pass
    os.remove(PID_FILE)


def _write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def _remove_pid():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start",    description="🏠 Главное меню"),
        BotCommand(command="workout",  description="💪 Тренировка"),
        BotCommand(command="food",     description="🍽 Записать питание"),
        BotCommand(command="summary",  description="📋 Сводка на сегодня"),
        BotCommand(command="stats",    description="📊 Статистика"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="reset",    description="🔄 Сбросить и перегенерировать программу"),
    ]
    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
        text="Открыть",
        web_app=WebAppInfo(url="https://oracle-bot-bot.duckdns.org/fitness/"),
    ))


async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(onboarding.router)
    dp.include_router(main_menu.router)
    dp.include_router(workout.router)
    dp.include_router(nutrition.router)
    dp.include_router(edit.router)
    dp.include_router(stats.router)
    dp.include_router(settings.router)
    dp.include_router(test_video.router)

    await set_bot_commands(bot)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    for uid in await get_all_onboarded_users():
        meals = await get_meal_reminders(uid)
        user = await get_user(uid)
        setup_daily_reminders(uid, meals)
        setup_workout_reminder(uid)
        if user and user.get("notify_morning_brief", 1):
            setup_morning_brief(uid, user.get("morning_brief_hour", 8), user.get("morning_brief_minute", 0))

    logger.info("Fitness Bot запущен")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    _kill_previous()
    _write_pid()
    try:
        asyncio.run(main())
    finally:
        _remove_pid()
