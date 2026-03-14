# database/repositories/ui_text_repository.py

"""
Репозиторий для работы с таблицей ui_texts.

Отвечает за:
- получение текстов по alias;
- получение кнопок;
- получение игровых кнопок;
- создание записей по умолчанию;
- мягкую дозапись новых служебных полей в старые записи;
- обновление текста.

Как работает:
- скрывает SQLAlchemy-запросы от обработчиков;
- предоставляет удобные методы работы с UI-текстами.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты UIText и коллекции объектов UIText.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.ui_text import UIText


class UITextRepository:
    """
    Репозиторий таблицы ui_texts.

    Отвечает за:
    - чтение UI-текстов;
    - чтение игровых кнопок;
    - создание и дозаполнение дефолтных записей;
    - изменение текстов.

    Как работает:
    - получает сессию в конструкторе;
    - выполняет ORM-запросы;
    - при изменениях делает commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - данные таблицы ui_texts в виде ORM-объектов.
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

    async def get_by_alias(self, alias: str) -> UIText | None:
        """
        Получает одну запись по alias.

        Что принимает:
        - alias: уникальный ключ текста.

        Что возвращает:
        - объект UIText или None.
        """

        result = await self.session.execute(
            select(UIText).where(UIText.alias == alias)
        )
        return result.scalar_one_or_none()

    async def get_many_by_aliases(self, aliases: list[str]) -> dict[str, UIText]:
        """
        Получает несколько записей по списку alias.

        Что принимает:
        - aliases: список alias.

        Что возвращает:
        - словарь alias -> UIText.
        """

        result = await self.session.execute(
            select(UIText).where(UIText.alias.in_(aliases))
        )
        rows = result.scalars().all()
        return {row.alias: row for row in rows}

    async def get_all_buttons(self) -> list[UIText]:
        """
        Получает все активные кнопки системы.

        Что принимает:
        - ничего.

        Что возвращает:
        - список объектов UIText.
        """

        result = await self.session.execute(
            select(UIText)
            .where(UIText.type == "button", UIText.is_active.is_(True))
            .order_by(UIText.id.asc())
        )
        return list(result.scalars().all())

    async def get_game_buttons(self, level: int, game: str | None = None) -> list[UIText]:
        """
        Получает игровые кнопки для указанного уровня меню.

        Что принимает:
        - level: уровень меню;
        - game: game_id игры или None.

        Что возвращает:
        - список кнопок UIText, отсортированных по order.
        """

        query = select(UIText).where(
            UIText.type == "button",
            UIText.is_active.is_(True),
            UIText.level == level,
        )

        if game is not None:
            query = query.where(UIText.game == game)

        query = query.order_by(UIText.order.asc(), UIText.id.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_next_order(self, game: str, level: int) -> int:
        """
        Возвращает следующий порядковый номер для игровой кнопки.

        Что принимает:
        - game: game_id игры;
        - level: уровень меню.

        Что возвращает:
        - следующий order для новой кнопки.
        """

        result = await self.session.execute(
            select(func.max(UIText.order)).where(
                UIText.game == game,
                UIText.level == level,
            )
        )
        max_order = result.scalar_one_or_none()
        if max_order is None:
            return 0
        return int(max_order) + 1

    async def create_if_missing(
        self,
        alias: str,
        value: str,
        text_type: str,
        description: str,
        game: str | None = None,
        level: int | None = None,
        order: int | None = None,
        game_alias: str | None = None,
    ) -> UIText:
        """
        Создаёт запись, если её ещё нет.

        Важная особенность:
        - если запись уже есть, метод мягко дозаполняет пустые новые поля,
          например game, level, order, game_alias.

        Что принимает:
        - alias: уникальный ключ;
        - value: текст;
        - text_type: тип записи;
        - description: описание;
        - game: game_id или None;
        - level: уровень меню или None;
        - order: порядок вывода или None;
        - game_alias: alias промта или None.

        Что возвращает:
        - существующий или созданный объект UIText.
        """

        existing = await self.get_by_alias(alias)
        if existing is not None:
            is_changed = False

            if existing.game is None and game is not None:
                existing.game = game
                is_changed = True

            if existing.level is None and level is not None:
                existing.level = level
                is_changed = True

            if existing.order is None and order is not None:
                existing.order = order
                is_changed = True

            if existing.game_alias is None and game_alias is not None:
                existing.game_alias = game_alias
                is_changed = True

            if is_changed:
                await self.session.commit()
                await self.session.refresh(existing)

            return existing

        item = UIText(
            alias=alias,
            value=value,
            type=text_type,
            description=description,
            game=game,
            level=level,
            order=order,
            game_alias=game_alias,
            is_active=True,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_value(self, alias: str, new_value: str) -> None:
        """
        Обновляет текст записи по alias.

        Что принимает:
        - alias: ключ записи;
        - new_value: новый текст.

        Что возвращает:
        - ничего.
        """

        item = await self.get_by_alias(alias)
        if item is None:
            return

        item.value = new_value
        await self.session.commit()