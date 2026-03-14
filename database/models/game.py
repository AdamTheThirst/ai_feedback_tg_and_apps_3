# database/models/game.py

"""
Модель таблицы games.

Отвечает за:
- хранение списка игр верхнего уровня;
- хранение системного game_id для связи с другими таблицами.

Как работает:
- name — название игры, которое пользователь видит в меню;
- game_id — системный идентификатор вида game_0, game_1 и т.д.

Что принимает:
- name игры;
- game_id игры.

Что возвращает:
- ORM-модель Game.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class Game(TimestampMixin, Base):
    """
    Таблица игр верхнего уровня.

    Отвечает за:
    - хранение списка игр;
    - предоставление game_id для связей с промтами, кнопками и диалогами.

    Как работает:
    - name отображается пользователю;
    - game_id используется как системный ключ в других таблицах.

    Что принимает:
    - name: отображаемое название игры;
    - game_id: системный идентификатор.

    Что возвращает:
    - объект ORM-модели Game.
    """

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    game_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)