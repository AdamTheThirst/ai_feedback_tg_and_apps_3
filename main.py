# main.py

"""
Точка входа в приложение.

Отвечает за:
- создание объекта бота;
- создание диспетчера;
- подключение роутеров;
- инициализацию базы данных;
- запуск polling.

Как работает:
- загружает настройки;
- подготавливает БД;
- регистрирует middleware для прокидывания сессии БД;
- запускает Telegram-бота.

Что принимает:
- ничего напрямую.

Что возвращает:
- ничего.
"""

import asyncio
import logging

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import TelegramObject

from bot.handlers.admin import router as admin_router
from bot.handlers.game import router as game_router
from bot.handlers.start import router as start_router
from config import settings
from database.bootstrap import prepare_database
from database.session import SessionFactory


class DatabaseSessionMiddleware(BaseMiddleware):
    """
    Middleware для прокидывания SQLAlchemy-сессии в обработчики.

    Отвечает за:
    - создание отдельной сессии БД на каждый входящий апдейт;
    - передачу этой сессии в handler через параметр session;
    - корректное закрытие сессии после завершения обработки.

    Как работает:
    - для каждого события открывает AsyncSession;
    - кладёт её в data под ключом session;
    - после обработки автоматически закрывает сессию.

    Что принимает:
    - handler: следующий обработчик в цепочке;
    - event: Telegram-событие;
    - data: словарь данных, пробрасываемый в handler.

    Что возвращает:
    - результат работы следующего обработчика.
    """

    async def __call__(
        self,
        handler,
        event: TelegramObject,
        data: dict,
    ):
        """
        Выполняет создание и внедрение сессии в текущую обработку апдейта.

        Что принимает:
        - handler: следующий обработчик;
        - event: объект Telegram-события;
        - data: словарь данных для handler.

        Что возвращает:
        - результат выполнения handler.
        """

        async with SessionFactory() as session:
            data["session"] = session
            return await handler(event, data)


async def main() -> None:
    """
    Главная асинхронная функция запуска приложения.

    Отвечает за:
    - подготовку базы данных;
    - создание бота и диспетчера;
    - подключение роутеров;
    - запуск polling.

    Как работает:
    - вызывает prepare_database;
    - настраивает Bot и Dispatcher;
    - регистрирует middleware;
    - запускает long polling.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    logging.basicConfig(level=logging.INFO)

    if not settings.bot_token:
        raise ValueError("Не найден BOT_TOKEN в .env")

    await prepare_database()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    dp.update.middleware(DatabaseSessionMiddleware())

    dp.include_router(start_router)
    dp.include_router(game_router)
    dp.include_router(admin_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())