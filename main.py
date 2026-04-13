import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, POLL_INTERVAL
from db.database import init_db
from bot.handlers import router
from scanner.monitor import start_monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не заданий у .env файлі")

    await init_db()
    logger.info("База даних ініціалізована")

    bot = Bot(token=BOT_TOKEN, default=None)
    dp = Dispatcher()
    dp.include_router(router)

    # Start background NFT scanner
    asyncio.create_task(start_monitor(bot, POLL_INTERVAL))

    logger.info("Бот запущений!")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
