# database/models/app_log.py

"""
Модель таблицы app_logs.

Отвечает за:
- хранение технических логов приложения;
- хранение уровня события;
- хранение расширяемого payload в JSON-строке.

Как работает:
- level хранит уровень логирования;
- event хранит короткий код события;
- source хранит источник лога;
- payload хранит расширяемые данные в JSON-строке.

Что принимает:
- данные лога.

Что возвращает:
- ORM-модель AppLog.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class AppLog(Base):
    """
    Таблица логов приложения.

    Отвечает за:
    - хранение событий приложения для последующего анализа;
    - мягкое расширение логов за счёт поля payload.

    Как работает:
    - payload хранится как JSON-строка;
    - при добавлении новых полей логики можно расширять payload,
      не меняя структуру таблицы.

    Что принимает:
    - level: уровень лога;
    - event: код события;
    - source: источник;
    - message: текст сообщения;
    - payload: JSON-строка с доп. данными;
    - created_at: время создания.

    Что возвращает:
    - объект ORM-модели AppLog.
    """

    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )