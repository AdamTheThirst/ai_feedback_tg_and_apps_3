# database/models/user.py

"""
Модель таблицы пользователей.

Отвечает за:
- хранение пользователя Telegram внутри бота;
- хранение пользовательского имени, введённого внутри бота;
- хранение даты регистрации.

Как работает:
- при первом /start система проверяет, есть ли пользователь в таблице;
- если пользователя нет, создаётся запись;
- имя может быть пустым до тех пор, пока пользователь его не введёт.

Что принимает:
- number_of_order: порядковый номер пользователя внутри бота;
- name: имя пользователя внутри бота;
- user_id: id пользователя Telegram;
- registration: дата и время регистрации.

Что возвращает:
- ORM-модель User.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class User(Base):
    """
    Таблица пользователей бота.

    Отвечает за:
    - хранение Telegram user_id;
    - хранение имени пользователя внутри бота;
    - хранение даты регистрации.

    Как работает:
    - user_id уникален;
    - number_of_order задаётся последовательно через репозиторий;
    - name может быть пустым до заполнения пользователем.

    Что принимает:
    - number_of_order: порядковый номер;
    - name: имя внутри бота;
    - user_id: id пользователя Telegram;
    - registration: дата регистрации.

    Что возвращает:
    - объект ORM-модели User.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number_of_order: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    registration: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
