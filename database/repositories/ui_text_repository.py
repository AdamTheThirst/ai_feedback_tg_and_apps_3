# app/database/repositories/ui_text_repository.py

"""
Файл: app/database/repositories/ui_text_repository.py

Репозиторий для работы с таблицей ui_texts.

Отвечает за:
- получение текстов по alias;
- получение текстов по type;
- создание текстов по умолчанию;
- обновление существующих текстов.

Как работает:
- инкапсулирует SQLAlchemy-запросы;
- упрощает работу обработчиков и сервисов.

Что принимает:
- активную AsyncSession.

Что возвращает:
- объекты UIText или коллекции текстов.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.ui_text import UIText


class UITextRepository:
    """
    Репозиторий для CRUD-операций над UI-текстами.

    Отвечает за:
    - чтение записей из таблицы ui_texts;
    - обновление текстов;
    - создание текстов по умолчанию.

    Как работает:
    - получает на вход SQLAlchemy-сессию;
    - выполняет нужные ORM-запросы;
    - при изменениях делает commit.

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
        Получает один UI-текст по его alias.

        Отвечает за:
        - поиск конкретной записи по уникальному ключу alias.

        Как работает:
        - выполняет select-запрос;
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
        Получает несколько UI-текстов по списку alias.

        Отвечает за:
        - пакетное получение набора текстов за один запрос.

        Как работает:
        - выполняет запрос с условием IN;
        - собирает результат в словарь alias -> UIText.

        Что принимает:
        - aliases: список alias.

        Что возвращает:
        - словарь с найденными объектами UIText.
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

    async def create_if_missing(
        self,
        alias: str,
        value: str,
        text_type: str,
        description: str,
    ) -> UIText:
        """
        Создаёт UI-текст, если его ещё нет в базе.

        Отвечает за:
        - первичное заполнение таблицы ui_texts начальными значениями.

        Как работает:
        - сначала пытается найти запись по alias;
        - если запись уже существует, возвращает её;
        - если записи нет, создаёт новую и делает commit.

        Что принимает:
        - alias: уникальный ключ;
        - value: текст;
        - text_type: тип записи, например button или text;
        - description: описание назначения.

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
        - если запись найдена, меняет поле value;
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