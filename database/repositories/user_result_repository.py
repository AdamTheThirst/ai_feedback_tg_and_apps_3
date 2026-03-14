# database/repositories/user_result_repository.py

"""
Репозиторий для работы с таблицей user_results.

Отвечает за:
- сохранение результатов аналитики пользователя;
- получение результатов пользователя при необходимости в будущем.

Как работает:
- после выполнения аналитики создаёт отдельную запись
  на каждый аналитический промт.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты UserResult.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.user_result import UserResult


class UserResultRepository:
    """
    Репозиторий таблицы user_results.

    Отвечает за:
    - запись результатов аналитики;
    - чтение результатов пользователя.

    Как работает:
    - использует активную SQLAlchemy-сессию;
    - при создании записи делает commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты UserResult.
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

    async def create_result(
        self,
        user_id: int,
        dialog_id: str,
        game_id: str,
        subgame_id: str,
        analitics_alias: str,
        analitics_score: float,
        analitics_text: str,
    ) -> UserResult:
        """
        Создаёт запись результата аналитики пользователя.

        Что принимает:
        - user_id: Telegram user id;
        - dialog_id: id диалога;
        - game_id: game_x;
        - subgame_id: alias игрового сценария;
        - analitics_alias: alias аналитического промта;
        - analitics_score: оценка по промту;
        - analitics_text: текст результата аналитики.

        Что возвращает:
        - созданный объект UserResult.
        """

        item = UserResult(
            user_id=user_id,
            dialog_id=dialog_id,
            game_id=game_id,
            subgame_id=subgame_id,
            analitics_alias=analitics_alias,
            analitics_score=analitics_score,
            analitics_text=analitics_text,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def list_by_user_id(self, user_id: int) -> list[UserResult]:
        """
        Получает все результаты конкретного пользователя.

        Что принимает:
        - user_id: Telegram user id.

        Что возвращает:
        - список объектов UserResult.
        """

        result = await self.session.execute(
            select(UserResult)
            .where(UserResult.user_id == user_id)
            .order_by(UserResult.id.asc())
        )
        return list(result.scalars().all())
