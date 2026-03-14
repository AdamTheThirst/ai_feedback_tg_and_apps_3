# app/database/repositories/password_repository.py

"""
Файл: app/database/repositories/password_repository.py

Репозиторий для работы с таблицей passwords.

Отвечает за:
- получение записи с паролем пользователя;
- создание записи с дефолтным хэшом;
- обновление хэша пароля.

Как работает:
- использует AsyncSession SQLAlchemy;
- скрывает детали запросов от обработчиков.

Что принимает:
- активную AsyncSession.

Что возвращает:
- объекты Password или результат обновления.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.password import Password


class PasswordRepository:
    """
    Репозиторий для таблицы passwords.

    Отвечает за:
    - поиск записи по user_id;
    - создание записи с дефолтным хэшем;
    - обновление хэша административного пароля.

    Как работает:
    - работает поверх ORM SQLAlchemy;
    - в изменяющих методах делает commit.

    Что принимает:
    - session: активная асинхронная сессия БД.

    Что возвращает:
    - ORM-объекты Password или None.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Инициализирует репозиторий.

        Что принимает:
        - session: активная асинхронная сессия БД.

        Что возвращает:
        - ничего.
        """

        self.session = session

    async def get_by_user_id(self, user_id: int) -> Password | None:
        """
        Получает запись с паролем по user_id.

        Отвечает за:
        - поиск пароля конкретного пользователя.

        Как работает:
        - выполняет select-запрос по user_id.

        Что принимает:
        - user_id: Telegram user id.

        Что возвращает:
        - объект Password или None.
        """

        result = await self.session.execute(
            select(Password).where(Password.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int, default_password_hash: str) -> Password:
        """
        Получает запись пользователя или создаёт её с дефолтным хэшем.

        Отвечает за:
        - инициализацию административного пароля для пользователя.

        Как работает:
        - сначала ищет запись по user_id;
        - если запись найдена, возвращает её;
        - если нет, создаёт новую запись с переданным хэшем.

        Что принимает:
        - user_id: Telegram user id;
        - default_password_hash: хэш дефолтного пароля.

        Что возвращает:
        - существующий или созданный объект Password.
        """

        existing = await self.get_by_user_id(user_id)
        if existing is not None:
            return existing

        item = Password(user_id=user_id, admin=default_password_hash)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_password_hash(self, user_id: int, new_password_hash: str) -> None:
        """
        Обновляет хэш пароля пользователя.

        Отвечает за:
        - сохранение нового административного пароля в виде хэша.

        Как работает:
        - ищет запись по user_id;
        - если запись есть, обновляет поле admin;
        - сохраняет изменения через commit.

        Что принимает:
        - user_id: Telegram user id;
        - new_password_hash: новый хэш пароля.

        Что возвращает:
        - ничего.
        """

        item = await self.get_by_user_id(user_id)
        if item is None:
            return

        item.admin = new_password_hash
        await self.session.commit()