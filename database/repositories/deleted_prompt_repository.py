# database/repositories/deleted_prompt_repository.py

"""
Репозиторий для работы с таблицей deleted_prompts.

Отвечает за:
- сохранение удалённых промтов в архивную таблицу.

Как работает:
- создаёт записи в deleted_prompts;
- сохраняет их через commit.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты DeletedPrompt.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.deleted_prompt import DeletedPrompt


class DeletedPromptRepository:
    """
    Репозиторий таблицы deleted_prompts.

    Отвечает за:
    - создание архивных записей удалённых промтов.

    Как работает:
    - получает сессию в конструкторе;
    - создаёт ORM-объект DeletedPrompt;
    - выполняет commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты DeletedPrompt.
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

    async def create(
        self,
        game_name: str,
        promt: str,
    ) -> DeletedPrompt:
        """
        Создаёт запись в архиве удалённых промтов.

        Что принимает:
        - game_name: название игры;
        - promt: текст промта.

        Что возвращает:
        - созданный объект DeletedPrompt.
        """

        item = DeletedPrompt(
            game_name=game_name,
            promt=promt,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item