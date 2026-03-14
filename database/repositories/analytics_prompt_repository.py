# database/repositories/analytics_prompt_repository.py

"""
Репозиторий для работы с таблицей analytics_prompts.

Отвечает за:
- создание аналитических промтов;
- получение одного аналитического промта;
- получение списка аналитических промтов;
- получение аналитических промтов по конкретной игре;
- обновление аналитического промта;
- удаление аналитического промта.

Как работает:
- инкапсулирует SQLAlchemy-запросы;
- скрывает детали работы с таблицей analytics_prompts.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты AnalyticsPrompt и коллекции AnalyticsPrompt.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.analytics_prompt import AnalyticsPrompt


class AnalyticsPromptRepository:
    """
    Репозиторий таблицы analytics_prompts.

    Отвечает за:
    - чтение аналитических промтов;
    - создание аналитических промтов;
    - изменение аналитических промтов;
    - удаление аналитических промтов.

    Как работает:
    - получает активную сессию в конструкторе;
    - выполняет ORM-запросы;
    - при изменениях делает commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты AnalyticsPrompt.
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

    async def get_by_alias(self, alias: str) -> AnalyticsPrompt | None:
        """
        Получает аналитический промт по alias.

        Что принимает:
        - alias: уникальный alias аналитики.

        Что возвращает:
        - объект AnalyticsPrompt или None.
        """

        result = await self.session.execute(
            select(AnalyticsPrompt).where(AnalyticsPrompt.alias == alias)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[AnalyticsPrompt]:
        """
        Получает список всех аналитических промтов.

        Что принимает:
        - ничего.

        Что возвращает:
        - список объектов AnalyticsPrompt.
        """

        result = await self.session.execute(
            select(AnalyticsPrompt).order_by(
                AnalyticsPrompt.game.asc(),
                AnalyticsPrompt.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_by_game(self, game_id: str) -> list[AnalyticsPrompt]:
        """
        Получает список аналитических промтов для конкретной игры.

        Как работает:
        - выбирает записи по полю game;
        - сортирует их по id в порядке создания.

        Что принимает:
        - game_id: системный game_id игры.

        Что возвращает:
        - список объектов AnalyticsPrompt.
        """

        result = await self.session.execute(
            select(AnalyticsPrompt)
            .where(AnalyticsPrompt.game == game_id)
            .order_by(AnalyticsPrompt.id.asc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        game: str,
        header: str,
        alias: str,
        comment: str,
        promt: str,
    ) -> AnalyticsPrompt:
        """
        Создаёт новый аналитический промт.

        Что принимает:
        - game: game_id игры;
        - header: заголовок;
        - alias: уникальный алиас;
        - comment: краткое описание;
        - promt: текст аналитического промта.

        Что возвращает:
        - созданный объект AnalyticsPrompt.
        """

        item = AnalyticsPrompt(
            game=game,
            header=header,
            alias=alias,
            comment=comment,
            promt=promt,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_prompt(
        self,
        alias: str,
        header: str,
        comment: str,
        promt: str,
    ) -> None:
        """
        Обновляет данные аналитического промта.

        Что принимает:
        - alias: alias аналитического промта;
        - header: новый заголовок;
        - comment: новый комментарий;
        - promt: новый текст промта.

        Что возвращает:
        - ничего.
        """

        item = await self.get_by_alias(alias)
        if item is None:
            return

        item.header = header
        item.comment = comment
        item.promt = promt
        await self.session.commit()

    async def delete_by_alias(self, alias: str) -> None:
        """
        Удаляет аналитический промт по alias.

        Что принимает:
        - alias: alias аналитического промта.

        Что возвращает:
        - ничего.
        """

        await self.session.execute(
            delete(AnalyticsPrompt).where(AnalyticsPrompt.alias == alias)
        )
        await self.session.commit()
