import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonCommands

from config import BOT_TOKEN
from database.db import init_db
from handlers import main_menu, nutrition, workout, onboarding, settings, stats, encyclopedia
from services.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log")]
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start",    description="🏠 Главное меню"),
        BotCommand(command="workout",  description="💪 Тренировка"),
        BotCommand(command="food",     description="🍽 Записать питание"),
        BotCommand(command="summary",  description="📋 Сводка на сегодня"),
        BotCommand(command="stats",    description="📊 Статистика"),
        BotCommand(command="settings", description="⚙️ Настройки"),
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
    dp.include_router(stats.router)
    dp.include_router(settings.router)
    dp.include_router(encyclopedia.router)

    await set_bot_commands(bot)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Fitness Bot запущен")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
