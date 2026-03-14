# main.py

"""
Точка входа в приложение.

Отвечает за:
- создание объекта бота;
- создание диспетчера;
- подключение роутеров;
- инициализацию базы данных;
- настройку логирования;
- запуск polling;
- настройку сервиса игровых таймеров.

Как работает:
- подготавливает БД;
- настраивает middleware с сессией БД;
- регистрирует роутеры;
- запускает long polling.

Что принимает:
- ничего.

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
from services.game_timer import configure_game_timer_service


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
    - настройку сервиса игровых таймеров;
    - запуск polling.

    Как работает:
    - вызывает prepare_database;
    - настраивает Bot и Dispatcher;
    - регистрирует middleware;
    - подключает сервис игровых таймеров;
    - запускает long polling.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if not settings.bot_token:
        raise ValueError("Не найден BOT_TOKEN в .env")

    await prepare_database()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    configure_game_timer_service(dp)

    dp.update.middleware(DatabaseSessionMiddleware())

    dp.include_router(start_router)
    dp.include_router(game_router)
    dp.include_router(admin_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())