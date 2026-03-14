# database/repositories/user_repository.py

"""
Репозиторий для работы с таблицей users.

Отвечает за:
- получение пользователя по Telegram user_id;
- создание пользователя при первом запуске;
- обновление имени пользователя;
- расчёт следующего порядкового номера пользователя.

Как работает:
- user_id считается уникальным идентификатором пользователя в Telegram;
- number_of_order считается последовательно через MAX + 1.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты User.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.user import User


class UserRepository:
    """
    Репозиторий таблицы users.

    Отвечает за:
    - чтение пользователя;
    - создание пользователя;
    - обновление имени пользователя.

    Как работает:
    - использует активную SQLAlchemy-сессию;
    - при изменениях выполняет commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты User.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Инициализирует репозиторий.

        Что принимает:
        - session: активная SQLAlchemy-сессия.

        Что возвращает:
        - ничего.
        """

        self.session = session

    async def get_by_user_id(self, user_id: int) -> User | None:
        """
        Получает пользователя по Telegram user_id.

        Что принимает:
        - user_id: Telegram user id.

        Что возвращает:
        - объект User или None.
        """

        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_next_number_of_order(self) -> int:
        """
        Вычисляет следующий порядковый номер пользователя.

        Что принимает:
        - ничего.

        Что возвращает:
        - следующий номер пользователя.
        """

        result = await self.session.execute(
            select(func.max(User.number_of_order))
        )
        max_value = result.scalar_one_or_none()

        if max_value is None:
            return 1

        return int(max_value) + 1

    async def create_placeholder(self, user_id: int) -> User:
        """
        Создаёт пользователя без имени.

        Как работает:
        - вычисляет number_of_order;
        - создаёт запись с пустым именем;
        - сохраняет дату регистрации автоматически.

        Что принимает:
        - user_id: Telegram user id.

        Что возвращает:
        - созданный объект User.
        """

        next_number = await self.get_next_number_of_order()

        item = User(
            number_of_order=next_number,
            name=None,
            user_id=user_id,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_name(self, user_id: int, name: str) -> None:
        """
        Обновляет имя пользователя.

        Что принимает:
        - user_id: Telegram user id;
        - name: новое имя пользователя.

        Что возвращает:
        - ничего.
        """

        user = await self.get_by_user_id(user_id)
        if user is None:
            return

        user.name = name
        await self.session.commit()
