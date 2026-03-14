# database/repositories/game_prompt_repository.py

"""
Репозиторий для работы с таблицей game_prompts.

Отвечает за:
- получение промта по alias;
- получение списка промтов по game_id;
- создание промта;
- создание дефолтного промта, если он отсутствует;
- обновление данных изображения;
- удаление промтов игры.

Как работает:
- скрывает SQLAlchemy-запросы от обработчиков;
- предоставляет единые методы для работы с промтами.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты GamePrompt.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.game_prompt import GamePrompt


class GamePromptRepository:
    """
    Репозиторий таблицы game_prompts.

    Отвечает за:
    - чтение промтов;
    - создание промтов;
    - обновление изображения у промта;
    - удаление промтов игры.

    Как работает:
    - работает поверх ORM SQLAlchemy;
    - в изменяющих методах делает commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты GamePrompt.
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

    async def get_by_alias(self, alias: str) -> GamePrompt | None:
        """
        Получает промт по alias.

        Что принимает:
        - alias: alias промта.

        Что возвращает:
        - объект GamePrompt или None.
        """

        result = await self.session.execute(
            select(GamePrompt).where(GamePrompt.alias == alias)
        )
        return result.scalar_one_or_none()

    async def list_by_game_id(self, game_id: str) -> list[GamePrompt]:
        """
        Получает все промты игры по game_id.

        Что принимает:
        - game_id: системный game_id игры.

        Что возвращает:
        - список объектов GamePrompt.
        """

        result = await self.session.execute(
            select(GamePrompt)
            .where(GamePrompt.game_id == game_id)
            .order_by(GamePrompt.id.asc())
        )
        return list(result.scalars().all())

    async def create_if_missing(
        self,
        game_id: str,
        alias: str,
        conditions: str,
        prompt_text: str,
        img_path: str | None = None,
        img_id: str | None = None,
        is_active: bool = True,
    ) -> GamePrompt:
        """
        Создаёт дефолтный промт, если его ещё нет.

        Что принимает:
        - game_id: game_id игры;
        - alias: alias промта;
        - conditions: условия сценария;
        - prompt_text: текст промта;
        - img_path: путь к изображению;
        - img_id: Telegram file_id;
        - is_active: признак активности.

        Что возвращает:
        - существующий или созданный объект GamePrompt.
        """

        existing = await self.get_by_alias(alias)
        if existing is not None:
            return existing

        item = GamePrompt(
            game_id=game_id,
            alias=alias,
            conditions=conditions,
            prompt_text=prompt_text,
            img_path=img_path,
            img_id=img_id,
            is_active=is_active,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def create(
        self,
        game_id: str,
        alias: str,
        conditions: str,
        prompt_text: str,
        img_path: str | None,
        img_id: str | None,
        is_active: bool = True,
    ) -> GamePrompt:
        """
        Создаёт новый промт.

        Что принимает:
        - game_id: game_id игры;
        - alias: alias промта;
        - conditions: условия сценария;
        - prompt_text: текст промта;
        - img_path: абсолютный путь к изображению;
        - img_id: Telegram file_id;
        - is_active: признак активности.

        Что возвращает:
        - созданный объект GamePrompt.
        """

        item = GamePrompt(
            game_id=game_id,
            alias=alias,
            conditions=conditions,
            prompt_text=prompt_text,
            img_path=img_path,
            img_id=img_id,
            is_active=is_active,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_image_data(
        self,
        alias: str,
        img_path: str | None,
        img_id: str | None,
    ) -> None:
        """
        Обновляет данные изображения у промта.

        Что принимает:
        - alias: alias промта;
        - img_path: путь к изображению;
        - img_id: Telegram file_id изображения.

        Что возвращает:
        - ничего.
        """

        item = await self.get_by_alias(alias)
        if item is None:
            return

        item.img_path = img_path
        item.img_id = img_id
        await self.session.commit()

    async def delete_by_game_id(self, game_id: str) -> None:
        """
        Удаляет все промты игры по game_id.

        Что принимает:
        - game_id: системный game_id игры.

        Что возвращает:
        - ничего.
        """

        await self.session.execute(
            delete(GamePrompt).where(GamePrompt.game_id == game_id)
        )
        await self.session.commit()