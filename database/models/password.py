# database/models/password.py

"""
Модель таблицы passwords.

Отвечает за:
- хранение административного пароля;
- хранение пароля только в виде хэша;
- привязку пароля к конкретному user_id.

Как работает:
- в таблице хранится user_id и хэш административного пароля;
- в текущей логике запись должна существовать для администратора с конкретным user_id.

Что принимает:
- user_id пользователя Telegram;
- admin — хэш пароля.

Что возвращает:
- ORM-модель Password.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class Password(TimestampMixin, Base):
    """
    Таблица с хэшами административных паролей.

    Отвечает за:
    - хранение пароля администратора в виде хэша;
    - привязку пароля к конкретному Telegram user_id.

    Как работает:
    - для каждого user_id может быть одна запись;
    - поле admin хранит именно хэш, а не открытый пароль.

    Что принимает:
    - user_id: Telegram user id;
    - admin: хэш пароля.

    Что возвращает:
    - объект ORM-модели Password.
    """

    __tablename__ = "passwords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    admin: Mapped[str] = mapped_column(String(128), nullable=False)