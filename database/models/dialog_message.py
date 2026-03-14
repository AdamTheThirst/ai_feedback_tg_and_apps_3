# database/models/dialog_message.py

"""
Модель таблицы dialog_messages.

Отвечает за:
- хранение всех сообщений диалога пользователя и ИИ;
- хранение общего dialog_id в рамках одной игровой сессии;
- хранение связки с игрой и подигрой.

Как работает:
- dialog_id общий для всех сообщений одного диалога;
- comment_owner принимает значения user или ai;
- game_id хранит игру верхнего уровня;
- subgame_id хранит alias конкретного промта.

Что принимает:
- данные одного сообщения диалога.

Что возвращает:
- ORM-модель DialogMessage.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class DialogMessage(Base):
    """
    Таблица сообщений диалога.

    Отвечает за:
    - хранение реплик пользователя и ИИ;
    - сохранение истории диалога в БД;
    - связывание реплик с игрой и сценарием.

    Как работает:
    - user и ai пишутся в поле comment_owner;
    - dialog_id объединяет сообщения одной игровой сессии.

    Что принимает:
    - user_id: Telegram user id;
    - dialog_id: id диалога;
    - comment_owner: owner сообщения;
    - comment: текст сообщения;
    - game_id: game_id верхнего уровня;
    - subgame_id: alias промта;
    - created_at: время создания.

    Что возвращает:
    - объект ORM-модели DialogMessage.
    """

    __tablename__ = "dialog_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    dialog_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    comment_owner: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    game_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subgame_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )