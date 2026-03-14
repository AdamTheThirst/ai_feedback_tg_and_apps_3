# database/repositories/game_repository.py

"""
Репозиторий для работы с таблицей games.

Отвечает за:
- получение списка игр;
- получение игры по game_id;
- создание игры;
- генерацию следующего game_id;
- создание дефолтных записей.

Как работает:
- инкапсулирует SQLAlchemy-запросы;
- скрывает детали работы с таблицей games.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты Game и коллекции Game.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.game import Game


class GameRepository:
    """
    Репозиторий таблицы games.

    Отвечает за:
    - чтение игр;
    - создание игр;
    - расчёт следующего game_id.

    Как работает:
    - получает активную сессию в конструкторе;
    - выполняет ORM-запросы;
    - при изменении данных делает commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты Game.
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

    async def list_all(self) -> list[Game]:
        """
        Получает список всех игр.

        Что принимает:
        - ничего.

        Что возвращает:
        - список объектов Game.
        """

        result = await self.session.execute(
            select(Game).order_by(Game.id.asc())
        )
        return list(result.scalars().all())

    async def get_by_game_id(self, game_id: str) -> Game | None:
        """
        Получает игру по её game_id.

        Что принимает:
        - game_id: системный game_id.

        Что возвращает:
        - объект Game или None.
        """

        result = await self.session.execute(
            select(Game).where(Game.game_id == game_id)
        )
        return result.scalar_one_or_none()

    async def create_if_missing(self, name: str, game_id: str) -> Game:
        """
        Создаёт игру, если её ещё нет.

        Что принимает:
        - name: название игры;
        - game_id: системный game_id.

        Что возвращает:
        - существующий или созданный объект Game.
        """

        existing = await self.get_by_game_id(game_id)
        if existing is not None:
            return existing

        item = Game(name=name, game_id=game_id)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def get_next_game_id(self) -> str:
        """
        Вычисляет следующий game_id в формате game_N.

        Что принимает:
        - ничего.

        Что возвращает:
        - строку следующего game_id.
        """

        games = await self.list_all()
        max_number = -1

        for game in games:
            match = re.fullmatch(r"game_(\d+)", game.game_id)
            if match:
                max_number = max(max_number, int(match.group(1)))

        return f"game_{max_number + 1}"

    async def create(self, name: str) -> Game:
        """
        Создаёт новую игру с автоматически вычисленным game_id.

        Что принимает:
        - name: название игры.

        Что возвращает:
        - созданный объект Game.
        """

        next_game_id = await self.get_next_game_id()

        item = Game(name=name, game_id=next_game_id)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item