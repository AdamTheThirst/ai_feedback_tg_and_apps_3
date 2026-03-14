# app/database/models/ui_text.py

"""
Файл: app/database/models/ui_text.py

Модель таблицы ui_texts.

Отвечает за:
- хранение всех UI-текстов системы;
- хранение подписей кнопок;
- возможность редактировать тексты через админку.

Как работает:
- каждая запись хранится в формате ключ-значение;
- поле alias используется как уникальный ключ;
- поле type показывает, это обычный текст или текст кнопки.

Что принимает:
- данные для UI-текста.

Что возвращает:
- ORM-модель UIText.
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class UIText(TimestampMixin, Base):
    """
    Таблица с UI-текстами приложения.

    Отвечает за:
    - хранение редактируемых текстов интерфейса;
    - хранение надписей на кнопках;
    - централизованное управление отображаемыми текстами.

    Как работает:
    - alias является уникальным идентификатором текста;
    - value содержит сам текст;
    - type хранит тип записи: button или text;
    - description объясняет, где этот текст используется.

    Что принимает:
    - alias: уникальный ключ текста;
    - value: значение текста;
    - type: тип текста;
    - description: описание назначения;
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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)