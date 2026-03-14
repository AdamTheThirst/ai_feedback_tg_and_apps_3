# database/models/admin_login_incident.py

"""
Модель таблицы инцидентов несанкционированного входа в админку.

Отвечает за:
- фиксацию попыток входа в админку с правильным паролем, но неправильным user_id;
- хранение данных пользователя на момент инцидента.

Как работает:
- при обнаружении такой попытки создаётся отдельная запись в таблице;
- Telegram Bot API не предоставляет надёжной информации об устройстве,
  поэтому поле device заполняется только если такая информация доступна.

Что принимает:
- user_id пользователя;
- username;
- first_name;
- last_name;
- device;
- attempted_at.

Что возвращает:
- ORM-модель AdminLoginIncident.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class AdminLoginIncident(TimestampMixin, Base):
    """
    Таблица инцидентов попыток несанкционированного входа в админку.

    Отвечает за:
    - хранение фактов несанкционированного входа;
    - хранение данных пользователя, который пытался войти;
    - сохранение времени инцидента.

    Как работает:
    - каждая подозрительная попытка создаёт новую запись в таблице.

    Что принимает:
    - user_id: Telegram user id;
    - username: username пользователя;
    - first_name: имя;
    - last_name: фамилия;
    - device: информация об устройстве, если доступна;
    - attempted_at: время попытки.

    Что возвращает:
    - объект ORM-модели AdminLoginIncident.
    """

    __tablename__ = "admin_login_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )