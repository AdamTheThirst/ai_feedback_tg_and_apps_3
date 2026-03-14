# database/repositories/ui_text_repository.py

"""
Репозиторий для работы с таблицей ui_texts.

Отвечает за:
- получение текстов по alias;
- получение наборов текстов по alias;
- получение всех кнопок;
- получение игровых кнопок по уровню;
- создание записей по умолчанию;
- обновление текста существующих записей.

Как работает:
- скрывает SQLAlchemy-запросы от обработчиков;
- предоставляет удобные методы для работы с UI-текстами.

Что принимает:
- активную AsyncSession.

Что возвращает:
- объекты UIText или коллекции объектов UIText.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.ui_text import UIText


class UITextRepository:
    """
    Репозиторий для таблицы ui_texts.

    Отвечает за:
    - чтение UI-текстов;
    - чтение игровых кнопок;
    - обновление значений текстов;
    - начальное создание записей.

    Как работает:
    - получает в конструкторе активную SQLAlchemy-сессию;
    - выполняет ORM-запросы;
    - при изменении данных делает commit.

    Что принимает:
    - session: активная асинхронная сессия БД.

    Что возвращает:
    - данные таблицы ui_texts в виде ORM-объектов.
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

    async def get_by_alias(self, alias: str) -> UIText | None:
        """
        Получает запись по alias.

        Отвечает за:
        - поиск одного UI-текста по уникальному ключу.

        Как работает:
        - выполняет select-запрос по alias;
        - возвращает найденный объект или None.

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

        Отвечает за:
        - пакетную выборку UI-текстов за один запрос.

        Как работает:
        - выполняет запрос с условием IN;
        - собирает результат в словарь alias -> объект.

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

        Отвечает за:
        - выборку всех записей типа button.

        Как работает:
        - фильтрует записи по type='button' и is_active=True;
        - сортирует результат по id.

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

        Отвечает за:
        - выборку кнопок, которые строят игровые меню динамически.

        Как работает:
        - выбирает только активные записи типа button;
        - фильтрует по level;
        - если передан game, дополнительно фильтрует по нему;
        - если game не передан, возвращает кнопки верхнего игрового уровня.

        Что принимает:
        - level: уровень меню;
        - game: alias игры или None.

        Что возвращает:
        - список кнопок UIText, отсортированных по полю order.
        """

        query = select(UIText).where(
            UIText.type == "button",
            UIText.is_active.is_(True),
            UIText.level == level,
        )

        if game is None:
            query = query.where(UIText.game.is_not(None))
        else:
            query = query.where(UIText.game == game)

        query = query.order_by(UIText.order.asc(), UIText.id.asc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_if_missing(
        self,
        alias: str,
        value: str,
        text_type: str,
        description: str,
        game: str | None = None,
        level: int | None = None,
        order: int | None = None,
    ) -> UIText:
        """
        Создаёт UI-текст, если его ещё нет в базе.

        Отвечает за:
        - первичное заполнение таблицы ui_texts начальными значениями.

        Как работает:
        - сначала ищет запись по alias;
        - если запись уже существует, возвращает её;
        - если записи нет, создаёт новую и делает commit.

        Что принимает:
        - alias: уникальный ключ;
        - value: текст;
        - text_type: тип записи, например button или text;
        - description: описание назначения;
        - game: alias игры или None;
        - level: уровень меню или None;
        - order: порядок вывода или None.

        Что возвращает:
        - существующий или созданный объект UIText.
        """

        existing = await self.get_by_alias(alias)
        if existing is not None:
            return existing

        item = UIText(
            alias=alias,
            value=value,
            type=text_type,
            description=description,
            game=game,
            level=level,
            order=order,
            is_active=True,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_value(self, alias: str, new_value: str) -> None:
        """
        Обновляет значение текста по alias.

        Отвечает за:
        - изменение текста или надписи кнопки в базе.

        Как работает:
        - ищет запись по alias;
        - если запись найдена, обновляет поле value;
        - сохраняет изменения через commit.

        Что принимает:
        - alias: ключ записи;
        - new_value: новое значение текста.

        Что возвращает:
        - ничего.
        """

        item = await self.get_by_alias(alias)
        if item is None:
            return

        item.value = new_value
        await self.session.commit()