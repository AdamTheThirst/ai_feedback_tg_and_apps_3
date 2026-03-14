# database/repositories/app_log_repository.py

"""
Репозиторий для работы с таблицей app_logs.

Отвечает за:
- сохранение логов приложения в базу данных.

Как работает:
- создаёт запись в app_logs;
- сохраняет её через commit.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объект AppLog.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.app_log import AppLog


class AppLogRepository:
    """
    Репозиторий таблицы app_logs.

    Отвечает за:
    - запись логов приложения в БД.

    Как работает:
    - получает сессию в конструкторе;
    - создаёт ORM-объект AppLog;
    - выполняет commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты AppLog.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Инициализирует репозиторий.

        Что принимает:
        - session: активная SQLAlchemy-сессия.

        Что возвращает:
        - ничего.
        """

        self.session = session

    async def create(
        self,
        level: str,
        event: str,
        source: str,
        message: str,
        payload: str | None = None,
    ) -> AppLog:
        """
        Создаёт запись лога.

        Что принимает:
        - level: уровень логирования;
        - event: код события;
        - source: источник;
        - message: текст сообщения;
        - payload: JSON-строка с доп. данными.

        Что возвращает:
        - созданный объект AppLog.
        """

        item = AppLog(
            level=level,
            event=event,
            source=source,
            message=message,
            payload=payload,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item