# database/models/analytics_prompt.py

"""
Модель таблицы analytics_prompts.

Отвечает за:
- хранение аналитических промтов;
- связь аналитического промта с конкретной игрой;
- хранение служебных полей для отображения в админке.

Как работает:
- поле game хранит game_id игры, например game_0;
- header используется как короткий заголовок;
- alias является уникальным идентификатором промта;
- comment кратко объясняет, что делает промт;
- promt хранит сам аналитический промт;
- modified_at автоматически обновляется при изменении записи.

Что принимает:
- game: game_id игры;
- header: краткий заголовок;
- alias: уникальный алиас;
- comment: короткое описание;
- promt: текст аналитического промта.

Что возвращает:
- ORM-модель AnalyticsPrompt.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class AnalyticsPrompt(Base):
    """
    Таблица аналитических промтов.

    Отвечает за:
    - хранение аналитических промтов для игр;
    - хранение короткого заголовка и описания;
    - хранение текста самого аналитического промта.

    Как работает:
    - каждая запись привязана к game_id;
    - alias уникален в рамках таблицы;
    - modified_at обновляется автоматически.

    Что принимает:
    - game: game_id игры;
    - header: короткий заголовок;
    - alias: уникальный алиас;
    - comment: краткое описание;
    - promt: текст аналитического промта.

    Что возвращает:
    - объект ORM-модели AnalyticsPrompt.
    """

    __tablename__ = "analytics_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    header: Mapped[str] = mapped_column(String(120), nullable=False)
    alias: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    comment: Mapped[str] = mapped_column(String(255), nullable=False)
    promt: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
