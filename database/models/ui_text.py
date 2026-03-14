# database/models/ui_text.py

"""
Модель таблицы ui_texts.

Отвечает за:
- хранение текстов интерфейса;
- хранение надписей на кнопках;
- хранение параметров игровых кнопок для динамического меню.

Как работает:
- alias — уникальный ключ текста;
- value — отображаемый текст;
- type — тип записи: text или button;
- game, level, order используются для построения игровых меню;
- game_alias связывает кнопку второго уровня с конкретным промтом.

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
    - хранение кнопок;
    - хранение параметров игровых кнопок.

    Как работает:
    - alias является уникальным идентификатором текста;
    - value содержит отображаемый текст;
    - type показывает, это кнопка или обычный текст;
    - game хранит game_id, например game_0;
    - level хранит уровень меню;
    - order хранит порядок показа;
    - game_alias связывает кнопку с конкретным промтом.

    Что принимает:
    - alias: уникальный ключ;
    - value: текст;
    - type: тип записи;
    - description: служебное описание;
    - game: game_id или null;
    - level: уровень меню или null;
    - order: порядок вывода или null;
    - game_alias: alias промта или null;
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
    order: Mapped[int | None] = mapped_column("order", Integer, nullable=True)
    game_alias: Mapped[str | None] = mapped_column(String(120), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)