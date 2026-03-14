# database/models/ui_text.py

"""
Модель таблицы ui_texts.

Отвечает за:
- хранение всех текстов интерфейса;
- хранение надписей на кнопках;
- хранение игровых кнопок с дополнительной разметкой по уровням меню.

Как работает:
- каждая запись хранится по принципу ключ-значение;
- alias — уникальный ключ;
- value — отображаемый текст;
- type — тип записи: text или button;
- game, level, order используются для динамического построения игровых меню.

Что принимает:
- данные UI-текста.

Что возвращает:
- ORM-модель UIText.
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class UIText(TimestampMixin, Base):
    """
    Таблица с текстами интерфейса.

    Отвечает за:
    - хранение сообщений интерфейса;
    - хранение надписей на кнопках;
    - хранение параметров игровых кнопок для динамического меню.

    Как работает:
    - alias является уникальным идентификатором текста;
    - value содержит отображаемый текст;
    - type показывает, это кнопка или текстовое сообщение;
    - game хранит alias игры, например game_0;
    - level хранит уровень меню:
      - 0 — главное меню игры;
      - 1 — внутреннее меню конкретной игры;
    - order хранит порядок показа кнопки в меню.

    Что принимает:
    - alias: уникальный ключ;
    - value: текст;
    - type: тип записи;
    - description: служебное описание;
    - game: alias игры или null;
    - level: уровень меню или null;
    - order: порядок показа или null;
    - is_active: флаг активности.

    Что возвращает:
    - объект ORM-модели UIText.
    """

    __tablename__ = "ui_texts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    game: Mapped[str | None] = mapped_column(String(50), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)