# app/database/bootstrap.py

"""
Файл: app/database/bootstrap.py

Инициализация базы данных и заполнение начальными данными.

Отвечает за:
- создание таблиц;
- заполнение таблицы ui_texts начальными значениями.

Как работает:
- при старте приложения создаёт таблицы, если их нет;
- затем добавляет обязательные UI-тексты, если их ещё нет.

Что принимает:
- ничего напрямую.

Что возвращает:
- ничего.
"""

from database.base import Base
from database.models import Password, UIText  # noqa: F401
from database.repositories.ui_text_repository import UITextRepository
from database.session import SessionFactory, engine


DEFAULT_UI_TEXTS: list[dict[str, str]] = [
    {
        "alias": "start_greeting",
        "value": "Привет, это текст приветствия первого экрана",
        "text_type": "text",
        "description": "Приветственное сообщение на экране /start",
    },
    {
        "alias": "admin_greeting",
        "value": "Привет, это админка",
        "text_type": "text",
        "description": "Приветственное сообщение главного меню админки",
    },
    {
        "alias": "admin_button_edit_start_greeting",
        "value": "Изменить приветствие главного экрана",
        "text_type": "button",
        "description": "Кнопка редактирования приветствия стартового экрана",
    },
    {
        "alias": "admin_button_edit_admin_greeting",
        "value": "Изменить приветствие админки",
        "text_type": "button",
        "description": "Кнопка редактирования приветствия админки",
    },
    {
        "alias": "admin_button_edit_buttons",
        "value": "Изменить текст на кнопках",
        "text_type": "button",
        "description": "Кнопка перехода к редактированию текстов кнопок",
    },
    {
        "alias": "admin_button_change_password",
        "value": "Изменить пароль админки",
        "text_type": "button",
        "description": "Кнопка запуска сценария смены пароля админки",
    },
    {
        "alias": "admin_button_exit",
        "value": "Выйти из админки",
        "text_type": "button",
        "description": "Кнопка выхода из админки",
    },
    {
        "alias": "common_edit_button",
        "value": "Изменить",
        "text_type": "button",
        "description": "Универсальная кнопка подтверждения перехода к редактированию текста",
    },
    {
        "alias": "common_cancel_button",
        "value": "Отмена",
        "text_type": "button",
        "description": "Универсальная кнопка отмены действия",
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
                alias=item["alias"],
                value=item["value"],
                text_type=item["text_type"],
                description=item["description"],
            )


async def prepare_database() -> None:
    """
    Полностью подготавливает базу данных к работе.

    Отвечает за:
    - создание таблиц;
    - начальное заполнение справочников.

    Как работает:
    - последовательно вызывает init_database и seed_ui_texts.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    await init_database()
    await seed_ui_texts()