# database/models/game_prompt.py

"""
Модель таблицы game_prompts.

Отвечает за:
- хранение промтов для игровых сценариев;
- хранение условий игры;
- хранение путей и Telegram file_id изображений;
- хранение признака активности промта.

Как работает:
- game_id связывает промт с конкретной игрой;
- alias — уникальный идентификатор промта;
- conditions — условия сценария;
- prompt_text — текст системного промта;
- img_path — абсолютный путь к изображению;
- img_id — Telegram file_id изображения;
- is_active — можно ли использовать промт.

Что принимает:
- данные промта.

Что возвращает:
- ORM-модель GamePrompt.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class GamePrompt(Base):
    """
    Таблица игровых промтов.

    Отвечает за:
    - хранение условий и промтов игровых сценариев;
    - хранение связанного изображения;
    - хранение статуса активности сценария.

    Как работает:
    - game_id связывает промт с игрой;
    - alias используется как уникальный ключ промта;
    - modified_at автоматически обновляется при изменении записи.

    Что принимает:
    - game_id: game_id игры;
    - alias: alias промта;
    - conditions: условия сценария;
    - prompt_text: текст системного промта;
    - img_path: путь к изображению;
    - img_id: Telegram file_id изображения;
    - is_active: признак активности.

    Что возвращает:
    - объект ORM-модели GamePrompt.
    """

    __tablename__ = "game_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    conditions: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    img_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    img_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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