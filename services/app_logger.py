# services/app_logger.py

"""
Сервис логирования приложения.

Отвечает за:
- вывод логов в консоль;
- при необходимости запись логов в таблицу app_logs.

Как работает:
- пишет лог в стандартный logging;
- при write_to_db=True сохраняет запись в app_logs отдельной сессией;
- payload хранит как JSON-строку, что позволяет мягко расширять структуру.

Что принимает:
- уровень лога;
- event;
- source;
- message;
- payload.

Что возвращает:
- ничего.
"""

import json
import logging

from database.repositories.app_log_repository import AppLogRepository
from database.session import SessionFactory


class AppLogger:
    """
    Универсальный сервис логирования.

    Отвечает за:
    - единый формат логов;
    - запись логов в консоль;
    - запись логов в БД.

    Как работает:
    - методы info, warning, error вызывают общий метод log;
    - для записи в БД используется отдельная сессия, чтобы не мешать основной бизнес-логике.

    Что принимает:
    - параметры события.

    Что возвращает:
    - ничего.
    """

    @staticmethod
    async def log(
        level: str,
        event: str,
        source: str,
        message: str,
        payload: dict | None = None,
        write_to_db: bool = True,
    ) -> None:
        """
        Записывает лог в консоль и при необходимости в БД.

        Что принимает:
        - level: уровень логирования;
        - event: код события;
        - source: источник;
        - message: текст сообщения;
        - payload: словарь с дополнительными данными;
        - write_to_db: нужно ли писать в БД.

        Что возвращает:
        - ничего.
        """

        logger = logging.getLogger(source)
        log_level = getattr(logging, level.upper(), logging.INFO)
        payload_text = json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else None

        logger.log(log_level, "%s | %s | payload=%s", event, message, payload_text)

        if not write_to_db:
            return

        try:
            async with SessionFactory() as session:
                repo = AppLogRepository(session)
                await repo.create(
                    level=level.upper(),
                    event=event,
                    source=source,
                    message=message,
                    payload=payload_text,
                )
        except Exception as error:  # noqa: BLE001
            logger.exception("Не удалось записать лог в БД: %s", error)

    @staticmethod
    async def info(
        event: str,
        source: str,
        message: str,
        payload: dict | None = None,
        write_to_db: bool = True,
    ) -> None:
        """
        Пишет INFO-лог.

        Что принимает:
        - event: код события;
        - source: источник;
        - message: текст;
        - payload: дополнительные данные;
        - write_to_db: писать ли в БД.

        Что возвращает:
        - ничего.
        """

        await AppLogger.log(
            level="INFO",
            event=event,
            source=source,
            message=message,
            payload=payload,
            write_to_db=write_to_db,
        )

    @staticmethod
    async def warning(
        event: str,
        source: str,
        message: str,
        payload: dict | None = None,
        write_to_db: bool = True,
    ) -> None:
        """
        Пишет WARNING-лог.

        Что принимает:
        - event: код события;
        - source: источник;
        - message: текст;
        - payload: дополнительные данные;
        - write_to_db: писать ли в БД.

        Что возвращает:
        - ничего.
        """

        await AppLogger.log(
            level="WARNING",
            event=event,
            source=source,
            message=message,
            payload=payload,
            write_to_db=write_to_db,
        )

    @staticmethod
    async def error(
        event: str,
        source: str,
        message: str,
        payload: dict | None = None,
        write_to_db: bool = True,
    ) -> None:
        """
        Пишет ERROR-лог.

        Что принимает:
        - event: код события;
        - source: источник;
        - message: текст;
        - payload: дополнительные данные;
        - write_to_db: писать ли в БД.

        Что возвращает:
        - ничего.
        """

        await AppLogger.log(
            level="ERROR",
            event=event,
            source=source,
            message=message,
            payload=payload,
            write_to_db=write_to_db,
        )