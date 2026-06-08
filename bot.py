import asyncio
import logging
import os
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonCommands

from config import BOT_TOKEN
from database.db import init_db, get_all_onboarded_users, get_meal_reminders
from handlers import main_menu, nutrition, workout, onboarding, settings, stats, edit
from services.scheduler import setup_scheduler, setup_daily_reminders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log")]
)
logger = logging.getLogger(__name__)

PID_FILE = "bot.pid"


def _kill_previous():
    my_pid = os.getpid()

    # Убиваем дубликаты через /proc (надёжнее PID-файла)
    try:
        for pid_str in os.listdir("/proc"):
            if not pid_str.isdigit():
                continue
            pid = int(pid_str)
            if pid == my_pid:
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmd = f.read().replace(b"\x00", b" ").decode(errors="ignore")
                if "fitness-bot" in cmd and "bot.py" in cmd:
                    os.kill(pid, signal.SIGTERM)
                    logger.info("Убит дублирующий процесс PID=%s", pid)
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                pass
    except Exception:
        pass

    # PID-файл как запасной вариант
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            if old_pid != my_pid:
                os.kill(old_pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass


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
        BotCommand(command="reset",    description="🔄 Сбросить программу"),
    ]
    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


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

    await set_bot_commands(bot)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    for uid in await get_all_onboarded_users():
        meals = await get_meal_reminders(uid)
        setup_daily_reminders(uid, meals)

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