# database/repositories/admin_login_incident_repository.py

"""
Репозиторий для работы с таблицей admin_login_incidents.

Отвечает за:
- создание записей об инцидентах несанкционированного входа в админку.

Как работает:
- принимает данные пользователя;
- создаёт новую запись в БД;
- сохраняет её через commit.

Что принимает:
- активную AsyncSession;
- данные об инциденте.

Что возвращает:
- созданный объект AdminLoginIncident.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.admin_login_incident import AdminLoginIncident


class AdminLoginIncidentRepository:
    """
    Репозиторий таблицы admin_login_incidents.

    Отвечает за:
    - создание и сохранение записей об инцидентах безопасности.

    Как работает:
    - получает сессию в конструкторе;
    - через отдельный метод создаёт новую запись в таблице.

    Что принимает:
    - session: активная асинхронная сессия БД.

    Что возвращает:
    - ORM-объекты AdminLoginIncident.
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

    async def create_incident(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        device: str | None,
    ) -> AdminLoginIncident:
        """
        Создаёт запись об инциденте безопасности.

        Отвечает за:
        - фиксацию попытки несанкционированного входа в админку.

        Как работает:
        - формирует ORM-объект AdminLoginIncident;
        - добавляет его в сессию;
        - выполняет commit;
        - возвращает созданную запись.

        Что принимает:
        - user_id: Telegram user id;
        - username: username пользователя;
        - first_name: имя пользователя;
        - last_name: фамилия пользователя;
        - device: данные об устройстве, если доступны.

        Что возвращает:
        - созданный объект AdminLoginIncident.
        """

        item = AdminLoginIncident(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            device=device,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item