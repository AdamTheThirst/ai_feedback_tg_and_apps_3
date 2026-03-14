# app/database/session.py

"""
Файл: app/database/session.py

Настройка подключения к базе данных.

Отвечает за:
- создание асинхронного движка SQLAlchemy;
- создание фабрики асинхронных сессий;
- предоставление функции для получения сессии.

Как работает:
- использует строку подключения из settings.database_url;
- создаёт AsyncSession через async_sessionmaker.

Что принимает:
- настройки из config.py.

Что возвращает:
- engine, SessionFactory и функцию get_session.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings


engine = create_async_engine(
    settings.database_url,
    echo=False,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Генератор асинхронной сессии базы данных.

    Отвечает за:
    - создание и корректное закрытие сессии SQLAlchemy.

    Как работает:
    - открывает сессию через SessionFactory;
    - после завершения работы автоматически закрывает её.

    Что принимает:
    - ничего.

    Что возвращает:
    - AsyncSession.
    """

    async with SessionFactory() as session:
        yield session