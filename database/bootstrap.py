# database/bootstrap.py

"""
Инициализация базы данных и заполнение начальными данными.

Отвечает за:
- создание таблиц;
- лёгкую миграцию таблицы ui_texts;
- заполнение таблицы ui_texts начальными значениями.

Как работает:
- при старте приложения создаёт таблицы, если их нет;
- затем проверяет наличие новых колонок в ui_texts;
- при необходимости добавляет недостающие поля;
- после этого добавляет обязательные UI-тексты.

Что принимает:
- ничего напрямую.

Что возвращает:
- ничего.
"""

from sqlalchemy import text

from database.base import Base
from database.models import AdminLoginIncident, Password, UIText  # noqa: F401
from database.repositories.ui_text_repository import UITextRepository
from database.session import SessionFactory, engine


DEFAULT_UI_TEXTS: list[dict[str, str | int | None]] = [
    {
        "alias": "start_greeting",
        "value": "Привет, это текст приветствия первого экрана",
        "text_type": "text",
        "description": "Приветственное сообщение на стартовом экране",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "admin_greeting",
        "value": "Привет, это админка",
        "text_type": "text",
        "description": "Приветственное сообщение главного меню админки",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "game_0_greeting",
        "value": "Основное приветствие Я-высказывания",
        "text_type": "text",
        "description": "Приветственное сообщение игрового меню Я-высказывание",
        "game": "game_0",
        "level": None,
        "order": None,
    },
    {
        "alias": "btn_first_level_game_0",
        "value": "Я-высказывание",
        "text_type": "button",
        "description": "Кнопка первого уровня для перехода в игру Я-высказывание",
        "game": "game_0",
        "level": 0,
        "order": 0,
    },
    {
        "alias": "btn_second_level_game_0_subordinate",
        "value": "Подчинённый",
        "text_type": "button",
        "description": "Кнопка второго уровня для выбора сценария Подчинённый в игре Я-высказывание",
        "game": "game_0",
        "level": 1,
        "order": 0,
    },
    {
        "alias": "btn_second_level_game_0_colleague",
        "value": "Коллега",
        "text_type": "button",
        "description": "Кнопка второго уровня для выбора сценария Коллега в игре Я-высказывание",
        "game": "game_0",
        "level": 1,
        "order": 1,
    },
    {
        "alias": "btn_encyclopedia",
        "value": "Энциклопедия",
        "text_type": "button",
        "description": "Кнопка-заглушка перехода в раздел Энциклопедия",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "btn_profile",
        "value": "Личный кабинет",
        "text_type": "button",
        "description": "Кнопка-заглушка перехода в раздел Личный кабинет",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "admin_button_edit_start_greeting",
        "value": "Изменить приветствие главного экрана",
        "text_type": "button",
        "description": "Кнопка редактирования приветствия стартового экрана",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "admin_button_edit_admin_greeting",
        "value": "Изменить приветствие админки",
        "text_type": "button",
        "description": "Кнопка редактирования приветствия админки",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "admin_button_edit_buttons",
        "value": "Изменить текст на кнопках",
        "text_type": "button",
        "description": "Кнопка перехода к редактированию текстов кнопок",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "admin_button_change_password",
        "value": "Изменить пароль админки",
        "text_type": "button",
        "description": "Кнопка запуска сценария смены пароля админки",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "admin_button_exit",
        "value": "Выйти из админки",
        "text_type": "button",
        "description": "Кнопка выхода из админки",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "common_edit_button",
        "value": "Изменить",
        "text_type": "button",
        "description": "Универсальная кнопка подтверждения редактирования",
        "game": None,
        "level": None,
        "order": None,
    },
    {
        "alias": "common_cancel_button",
        "value": "Отмена",
        "text_type": "button",
        "description": "Универсальная кнопка отмены",
        "game": None,
        "level": None,
        "order": None,
    },
]


async def init_database() -> None:
    """
    Создаёт таблицы базы данных, если их ещё нет.

    Отвечает за:
    - создание структуры БД на старте приложения.

    Как работает:
    - открывает соединение с БД;
    - вызывает metadata.create_all для всех зарегистрированных моделей.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def migrate_ui_texts_table() -> None:
    """
    Выполняет лёгкую миграцию таблицы ui_texts.

    Отвечает за:
    - добавление новых колонок game, level и order в уже существующую таблицу.

    Как работает:
    - читает список колонок через PRAGMA table_info;
    - если нужной колонки нет, добавляет её через ALTER TABLE.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    async with engine.begin() as connection:
        result = await connection.execute(text("PRAGMA table_info(ui_texts)"))
        rows = result.fetchall()
        existing_columns = {row[1] for row in rows}

        if "game" not in existing_columns:
            await connection.execute(text("ALTER TABLE ui_texts ADD COLUMN game VARCHAR(50)"))

        if "level" not in existing_columns:
            await connection.execute(text("ALTER TABLE ui_texts ADD COLUMN level INTEGER"))

        if "order" not in existing_columns:
            await connection.execute(text('ALTER TABLE ui_texts ADD COLUMN "order" INTEGER'))


async def seed_ui_texts() -> None:
    """
    Заполняет таблицу ui_texts начальными данными.

    Отвечает за:
    - добавление обязательных UI-текстов при первом запуске.

    Как работает:
    - открывает сессию;
    - проходит по набору DEFAULT_UI_TEXTS;
    - создаёт запись только если её ещё нет.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    async with SessionFactory() as session:
        repo = UITextRepository(session)

        for item in DEFAULT_UI_TEXTS:
            await repo.create_if_missing(
                alias=str(item["alias"]),
                value=str(item["value"]),
                text_type=str(item["text_type"]),
                description=str(item["description"]),
                game=item["game"] if isinstance(item["game"], str) or item["game"] is None else None,
                level=item["level"] if isinstance(item["level"], int) or item["level"] is None else None,
                order=item["order"] if isinstance(item["order"], int) or item["order"] is None else None,
            )


async def prepare_database() -> None:
    """
    Полностью подготавливает базу данных к работе.

    Отвечает за:
    - создание таблиц;
    - миграцию ui_texts;
    - начальное заполнение справочников.

    Как работает:
    - последовательно вызывает init_database, migrate_ui_texts_table и seed_ui_texts.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    await init_database()
    await migrate_ui_texts_table()
    await seed_ui_texts()