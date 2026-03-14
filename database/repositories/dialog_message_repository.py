# database/repositories/dialog_message_repository.py

"""
Репозиторий для работы с таблицей dialog_messages.

Отвечает за:
- сохранение сообщений диалога;
- получение последних сообщений диалога для контекста ИИ;
- удаление сообщений по игре.

Как работает:
- добавляет новые строки в таблицу dialog_messages;
- выбирает последние сообщения по dialog_id;
- удаляет сообщения по game_id.

Что принимает:
- активную AsyncSession.

Что возвращает:
- ORM-объекты DialogMessage и коллекции объектов.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.dialog_message import DialogMessage


class DialogMessageRepository:
    """
    Репозиторий таблицы dialog_messages.

    Отвечает за:
    - запись реплик диалога;
    - чтение последних реплик диалога;
    - удаление сообщений игры.

    Как работает:
    - использует ORM SQLAlchemy;
    - при добавлении новой записи делает commit.

    Что принимает:
    - session: активная SQLAlchemy-сессия.

    Что возвращает:
    - ORM-объекты DialogMessage.
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

    async def create_message(
        self,
        user_id: int,
        dialog_id: str,
        comment_owner: str,
        comment: str,
        game_id: str,
        subgame_id: str,
    ) -> DialogMessage:
        """
        Сохраняет сообщение диалога.

        Что принимает:
        - user_id: Telegram user id;
        - dialog_id: id диалога;
        - comment_owner: user или ai;
        - comment: текст сообщения;
        - game_id: game_id игры;
        - subgame_id: alias промта.

        Что возвращает:
        - созданный объект DialogMessage.
        """

        item = DialogMessage(
            user_id=user_id,
            dialog_id=dialog_id,
            comment_owner=comment_owner,
            comment=comment,
            game_id=game_id,
            subgame_id=subgame_id,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def get_recent_messages(
        self,
        dialog_id: str,
        limit: int = 30,
    ) -> list[DialogMessage]:
        """
        Получает последние сообщения диалога.

        Что принимает:
        - dialog_id: id диалога;
        - limit: максимальное число сообщений.

        Что возвращает:
        - список последних сообщений в хронологическом порядке.
        """

        result = await self.session.execute(
            select(DialogMessage)
            .where(DialogMessage.dialog_id == dialog_id)
            .order_by(DialogMessage.id.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def delete_by_game_id(self, game_id: str) -> None:
        """
        Удаляет все сообщения игры по game_id.

        Что принимает:
        - game_id: системный game_id игры.

        Что возвращает:
        - ничего.
        """

        await self.session.execute(
            delete(DialogMessage).where(DialogMessage.game_id == game_id)
        )
        await self.session.commit()