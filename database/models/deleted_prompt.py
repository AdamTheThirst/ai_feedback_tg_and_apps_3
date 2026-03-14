# database/models/deleted_prompt.py

"""
Модель таблицы deleted_prompts.

Отвечает за:
- хранение удалённых промтов;
- сохранение названия игры и текста промта перед удалением.

Как работает:
- при удалении промта или игры связанный промт переносится в эту таблицу;
- таблица хранит минимально необходимую информацию для архива.

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
    - архивирование промтов перед окончательным удалением.

    Как работает:
    - каждая запись содержит название игры и текст промта.

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