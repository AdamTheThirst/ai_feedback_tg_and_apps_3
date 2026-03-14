# database/models/deleted_prompt.py

"""
Модель таблицы deleted_prompts.

Отвечает за:
- хранение удалённых промтов перед удалением игры;
- сохранение текста промта и названия игры.

Как работает:
- перед удалением игры связанные с ней промты переносятся в эту таблицу;
- в таблице хранится только минимально нужная информация.

Что принимает:
- game_name: название игры;
- promt: текст промта.

Что возвращает:
- ORM-модель DeletedPrompt.
"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class DeletedPrompt(Base):
    """
    Таблица удалённых промтов.

    Отвечает за:
    - архивирование промтов перед удалением игры.

    Как работает:
    - в каждую запись кладётся название игры и текст промта.

    Что принимает:
    - game_name: человекочитаемое название игры;
    - promt: текст промта.

    Что возвращает:
    - объект ORM-модели DeletedPrompt.
    """

    __tablename__ = "deleted_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_name: Mapped[str] = mapped_column(String(255), nullable=False)
    promt: Mapped[str] = mapped_column(Text, nullable=False)