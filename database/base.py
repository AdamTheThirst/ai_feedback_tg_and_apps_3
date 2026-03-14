# app/database/base.py

"""
Файл: app/database/base.py

Базовые сущности для моделей SQLAlchemy.

Отвечает за:
- создание общего базового класса моделей;
- добавление универсального миксина со служебными полями времени.

Как работает:
- все модели наследуются от Base;
- для важных сущностей используется TimestampMixin.

Что принимает:
- ничего напрямую.

Что возвращает:
- классы Base и TimestampMixin для наследования.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Базовый класс для всех ORM-моделей.

    Отвечает за:
    - регистрацию моделей в metadata SQLAlchemy;
    - возможность централизованно создавать таблицы.

    Как работает:
    - все ORM-модели проекта наследуются от этого класса.

    Что принимает:
    - ничего.

    Что возвращает:
    - базовый класс для декларативных моделей.
    """


class TimestampMixin:
    """
    Миксин со служебными полями времени.

    Отвечает за:
    - автоматическое хранение времени создания записи;
    - автоматическое хранение времени последнего обновления записи.

    Как работает:
    - при создании записи оба поля заполняются текущим временем;
    - при обновлении записи поле updated_at обновляется автоматически.

    Что принимает:
    - ничего.

    Что возвращает:
    - набор общих полей для наследования в моделях.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )