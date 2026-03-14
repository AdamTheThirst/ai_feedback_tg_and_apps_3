# app/database/models/password.py

"""
Файл: app/database/models/password.py

Модель таблицы passwords.

Отвечает за:
- хранение пароля администратора для пользователя;
- хранение именно хэша пароля, а не открытого текста.

Как работает:
- для каждого пользователя может быть одна запись;
- поле admin хранит хэш пароля;
- по умолчанию при первом входе в /admin создаётся запись с паролем 123 в виде хэша.

Что принимает:
- user_id пользователя Telegram;
- admin — хэш пароля администратора.

Что возвращает:
- ORM-модель Password.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class Password(TimestampMixin, Base):
    """
    Таблица с хэшами административных паролей пользователей.

    Отвечает за:
    - хранение пароля администратора в виде хэша;
    - привязку пароля к конкретному пользователю.

    Как работает:
    - у каждого user_id одна запись;
    - в поле admin хранится не обычный пароль, а его хэш.

    Что принимает:
    - user_id: id пользователя Telegram;
    - admin: хэш пароля.

    Что возвращает:
    - объект ORM-модели Password.
    """

    __tablename__ = "passwords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    admin: Mapped[str] = mapped_column(String(128), nullable=False)