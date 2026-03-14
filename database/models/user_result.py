# database/models/user_result.py

"""
Модель таблицы результатов аналитики пользователя.

Отвечает за:
- хранение результата каждого аналитического промта;
- привязку результата к пользователю;
- привязку результата к конкретному диалогу;
- привязку результата к игре и подигре.

Как работает:
- после завершения диалога и выполнения аналитики
  для каждого аналитического промта создаётся отдельная запись;
- в таблицу пишется алиас аналитики, оценка и текст результата.

Что принимает:
- user_id: Telegram id пользователя;
- dialog_id: id диалога;
- game_id: game_x;
- subgame_id: alias игрового промта;
- analitics_alias: alias аналитического промта;
- analitics_score: баллы по аналитике;
- analitics_text: текст результата аналитики;
- create_at: время создания записи.

Что возвращает:
- ORM-модель UserResult.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class UserResult(Base):
    """
    Таблица результатов аналитики пользователя.

    Отвечает за:
    - хранение оценки по каждому аналитическому промту;
    - хранение текста аналитики;
    - хранение связки пользователь-диалог-игра-аналитика.

    Как работает:
    - одна запись соответствует одному результату одного аналитического промта;
    - dialog_id позволяет собрать все результаты конкретного диалога.

    Что принимает:
    - user_id: Telegram id пользователя;
    - dialog_id: id диалога;
    - game_id: game_x;
    - subgame_id: alias игрового сценария;
    - analitics_alias: alias аналитического промта;
    - analitics_score: оценка;
    - analitics_text: текст аналитики;
    - create_at: время создания записи.

    Что возвращает:
    - объект ORM-модели UserResult.
    """

    __tablename__ = "user_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    dialog_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    game_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subgame_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    analitics_alias: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    analitics_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    analitics_text: Mapped[str] = mapped_column(Text, nullable=False)
    create_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
