# run.py
import asyncio
import logging
import os
from pathlib import Path
from aiohttp import web

from app.webui import create_web_app
from config import settings
from aiogram import Bot, Dispatcher
from app.user import user
from app.admin import admin
from app.files import router as files_router
from app.payment_handlers import payment_router
from app.payment_webhook import setup_payment_routes
from app.scheduler import start_scheduler

# >>> ДОБАВЬ ЭТО:
from sqlalchemy.ext.asyncio import create_async_engine
from app.database.models import Base  # тут лежат твои модели (User, и т.д.)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )

async def start_web(bot: Bot):
    app = create_web_app(UPLOAD_DIR)
    
    # Добавляем бот в app для использования в webhook
    app["bot"] = bot
    
    # Регистрируем маршруты для платежей
    setup_payment_routes(app)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    print(f"Starting web UI on 0.0.0.0:8000, uploads at {UPLOAD_DIR}")

# >>> ДОБАВЬ ЭТО:
async def init_db():
    """
    Создаёт все таблицы по моделям SQLAlchemy, если их ещё нет.
    Берёт DSN из settings.DATABASE_URL (например:
    postgresql+asyncpg://postgres:postgres@db:5432/postgres)
    """
    engine = create_async_engine(settings.DB_URL, future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

async def main():
    _configure_logging()
    # сначала – инициализация БД
    await init_db()

    bot = Bot(token=settings.TOKEN)
    dp = Dispatcher()
    dp.include_router(admin)
    dp.include_router(user)
    dp.include_router(files_router)
    dp.include_router(payment_router)  # Добавляем роутер для платежей
    
    # Запускаем планировщик для проверки подписок
    start_scheduler(bot)

    await asyncio.gather(
        start_web(bot),
        dp.start_polling(bot),
    )

if __name__ == "__main__":
    asyncio.run(main())
