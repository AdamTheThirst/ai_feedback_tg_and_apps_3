# database/bootstrap.py

"""
Инициализация базы данных и заполнение начальными данными.

Отвечает за:
- создание таблиц;
- мягкую миграцию ui_texts;
- заполнение таблиц начальными значениями.

Как работает:
- создаёт таблицы, если их ещё нет;
- добавляет недостающие колонки в ui_texts;
- создаёт дефолтную игру game_0;
- создаёт дефолтные игровые промты;
- создаёт UI-тексты по умолчанию.

Что принимает:
- ничего.

Что возвращает:
- ничего.
"""

from sqlalchemy import text

from database.base import Base
from database.models import (
    AdminLoginIncident,
    AnalyticsPrompt,
    AppLog,
    DeletedPrompt,
    DialogMessage,
    Game,
    GamePrompt,
    Password,
    UIText,
)  # noqa: F401
from database.repositories.game_prompt_repository import GamePromptRepository
from database.repositories.game_repository import GameRepository
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
        "game_alias": None,
    },
    {
        "alias": "admin_greeting",
        "value": "Привет, это админка",
        "text_type": "text",
        "description": "Приветственное сообщение главного меню админки",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "game_0_greeting",
        "value": "Основное приветствие Я-высказывания",
        "text_type": "text",
        "description": "Приветствие меню игры Я-высказывание",
        "game": "game_0",
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "btn_encyclopedia",
        "value": "Энциклопедия",
        "text_type": "button",
        "description": "Кнопка-заглушка раздела Энциклопедия",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "btn_profile",
        "value": "Личный кабинет",
        "text_type": "button",
        "description": "Кнопка-заглушка раздела Личный кабинет",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "btn_second_level_game_0_subordinate",
        "value": "Подчинённый",
        "text_type": "button",
        "description": "Кнопка второго уровня сценария Подчинённый",
        "game": "game_0",
        "level": 1,
        "order": 0,
        "game_alias": "game_alias_subordinate",
    },
    {
        "alias": "btn_second_level_game_0_colleague",
        "value": "Коллега",
        "text_type": "button",
        "description": "Кнопка второго уровня сценария Коллега",
        "game": "game_0",
        "level": 1,
        "order": 1,
        "game_alias": "game_alias_colleague",
    },
    {
        "alias": "greeting_game_alias_subordinate",
        "value": "Это приветствие Подчинённого",
        "text_type": "text",
        "description": "Приветствие игрового сценария Подчинённый",
        "game": "game_0",
        "level": None,
        "order": None,
        "game_alias": "game_alias_subordinate",
    },
    {
        "alias": "greeting_game_alias_colleague",
        "value": "Это приветствие Коллеги",
        "text_type": "text",
        "description": "Приветствие игрового сценария Коллега",
        "game": "game_0",
        "level": None,
        "order": None,
        "game_alias": "game_alias_colleague",
    },
    {
        "alias": "thinking_message",
        "value": "[Думаю...]",
        "text_type": "text",
        "description": "Сообщение во время ожидания ответа ИИ",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "finish_feedback_button",
        "value": "Дай обратную связь",
        "text_type": "button",
        "description": "Кнопка завершения игрового диалога",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "game_inactive_message",
        "value": "Игра пока не активна",
        "text_type": "text",
        "description": "Сообщение, если промт не активен",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "dialog_finished_message",
        "value": "Диалог завершён.\nВозвращаю к выбору сценария.",
        "text_type": "text",
        "description": "Сообщение после ручного завершения диалога",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "dialog_timeout_message",
        "value": "Время диалога истекло.\nВозвращаю к выбору сценария.",
        "text_type": "text",
        "description": "Сообщение после автоматического завершения диалога по таймеру",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "analysis_in_progress_message",
        "value": "Идёт анализ. Это может занять несколько минут, пожалуйста, подождите",
        "text_type": "text",
        "description": "Сообщение пользователю на время выполнения аналитики завершённого диалога",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "analysis_no_prompts_message",
        "value": "Для этой игры пока не настроена аналитика.",
        "text_type": "text",
        "description": "Сообщение, если для игры не найдено ни одного аналитического промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "analysis_empty_dialog_message",
        "value": "Не удалось найти сообщения диалога для анализа.",
        "text_type": "text",
        "description": "Сообщение, если диалог пуст и аналитика невозможна",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "analysis_total_score_message",
        "value": "Общая сумма баллов: {score}",
        "text_type": "text",
        "description": "Сообщение с общей суммой баллов по завершении аналитики",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_edit_start_greeting",
        "value": "Изменить приветствие главного экрана",
        "text_type": "button",
        "description": "Кнопка редактирования приветствия стартового экрана",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_edit_admin_greeting",
        "value": "Изменить приветствие админки",
        "text_type": "button",
        "description": "Кнопка редактирования приветствия админки",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_edit_buttons",
        "value": "Изменить текст на кнопках",
        "text_type": "button",
        "description": "Кнопка редактирования текстов кнопок",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_change_password",
        "value": "Изменить пароль админки",
        "text_type": "button",
        "description": "Кнопка смены пароля админки",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_prompt_games_work",
        "value": "Работа с промтами и играми",
        "text_type": "button",
        "description": "Кнопка перехода в раздел работы с промтами и играми",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_analytics",
        "value": "Анализ",
        "text_type": "button",
        "description": "Кнопка перехода в раздел аналитики",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_analytics_new",
        "value": "Новая аналитика",
        "text_type": "button",
        "description": "Кнопка добавления новой аналитики",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_analytics_edit",
        "value": "Изменить аналитику",
        "text_type": "button",
        "description": "Кнопка изменения аналитики",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_analytics_delete",
        "value": "Удалить аналитику",
        "text_type": "button",
        "description": "Кнопка удаления аналитики",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_analytics_back",
        "value": "Назад",
        "text_type": "button",
        "description": "Кнопка возврата из раздела аналитики в главное меню админки",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_analytics_add_one_more",
        "value": "Ещё один промт в эту аналитику",
        "text_type": "button",
        "description": "Кнопка добавления ещё одного аналитического промта в ту же игру",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_tools_add_game",
        "value": "Добавить игру",
        "text_type": "button",
        "description": "Кнопка добавления новой игры",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_tools_add_prompt",
        "value": "Добавить промт",
        "text_type": "button",
        "description": "Кнопка добавления нового промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_tools_edit_prompts",
        "value": "Изменить промты",
        "text_type": "button",
        "description": "Кнопка изменения существующих промтов",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_tools_toggle_prompt",
        "value": "Активировать/деактивировать",
        "text_type": "button",
        "description": "Кнопка переключения активности промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_tools_delete_prompt",
        "value": "Удалить промт",
        "text_type": "button",
        "description": "Кнопка удаления промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_tools_delete_game",
        "value": "Удалить игру",
        "text_type": "button",
        "description": "Кнопка удаления игры",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_tools_back",
        "value": "Назад",
        "text_type": "button",
        "description": "Кнопка возврата в главное меню админки из раздела работы с промтами и играми",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_prompt_action_name",
        "value": "Изменить название",
        "text_type": "button",
        "description": "Кнопка изменения названия кнопки промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_prompt_action_conditions",
        "value": "Изменить условия",
        "text_type": "button",
        "description": "Кнопка изменения условий промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_prompt_action_prompt",
        "value": "Изменить промт",
        "text_type": "button",
        "description": "Кнопка изменения текста промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_prompt_action_image",
        "value": "Изменить изображение",
        "text_type": "button",
        "description": "Кнопка изменения изображения промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_skip_image",
        "value": "Пропустить изображение",
        "text_type": "button",
        "description": "Кнопка пропуска загрузки изображения для промта",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "admin_button_exit",
        "value": "Выйти из админки",
        "text_type": "button",
        "description": "Кнопка выхода из админки",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "common_edit_button",
        "value": "Изменить",
        "text_type": "button",
        "description": "Универсальная кнопка подтверждения редактирования",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "common_delete_button",
        "value": "Удалить",
        "text_type": "button",
        "description": "Универсальная кнопка удаления",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
    {
        "alias": "common_cancel_button",
        "value": "Отмена",
        "text_type": "button",
        "description": "Универсальная кнопка отмены действия",
        "game": None,
        "level": None,
        "order": None,
        "game_alias": None,
    },
]

DEFAULT_GAMES: list[dict[str, str]] = [
    {
        "name": "Я-высказывание",
        "game_id": "game_0",
    },
]

DEFAULT_PROMPTS: list[dict[str, str | bool | None]] = [
    {
        "game_id": "game_0",
        "alias": "game_alias_subordinate",
        "conditions": "Это условия для Подчинённого",
        "prompt_text": "Ты - ассистент. Ты умеешь только здороваться и говорить комплименты.",
        "img_path": None,
        "img_id": None,
        "is_active": True,
    },
    {
        "game_id": "game_0",
        "alias": "game_alias_colleague",
        "conditions": "Это условия для Коллеги",
        "prompt_text": "Ты - ассистент. Ты умеешь только здороваться и говорить комплименты.",
        "img_path": None,
        "img_id": None,
        "is_active": True,
    },
]


async def init_database() -> None:
    """
    Создаёт таблицы БД, если их ещё нет.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def migrate_ui_texts_table() -> None:
    """
    Мягко мигрирует таблицу ui_texts.

    Добавляет недостающие колонки:
    - game
    - level
    - order
    - game_alias

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

        if "game_alias" not in existing_columns:
            await connection.execute(text("ALTER TABLE ui_texts ADD COLUMN game_alias VARCHAR(120)"))


async def seed_games() -> None:
    """
    Заполняет таблицу games дефолтными значениями.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    async with SessionFactory() as session:
        repo = GameRepository(session)

        for item in DEFAULT_GAMES:
            await repo.create_if_missing(
                name=item["name"],
                game_id=item["game_id"],
            )


async def seed_prompts() -> None:
    """
    Заполняет таблицу game_prompts дефолтными значениями.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    async with SessionFactory() as session:
        repo = GamePromptRepository(session)

        for item in DEFAULT_PROMPTS:
            await repo.create_if_missing(
                game_id=str(item["game_id"]),
                alias=str(item["alias"]),
                conditions=str(item["conditions"]),
                prompt_text=str(item["prompt_text"]),
                img_path=item["img_path"] if isinstance(item["img_path"], str) or item["img_path"] is None else None,
                img_id=item["img_id"] if isinstance(item["img_id"], str) or item["img_id"] is None else None,
                is_active=bool(item["is_active"]),
            )


async def seed_ui_texts() -> None:
    """
    Заполняет таблицу ui_texts начальными данными.

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
                game_alias=item["game_alias"] if isinstance(item["game_alias"], str) or item["game_alias"] is None else None,
            )


async def prepare_database() -> None:
    """
    Полностью подготавливает базу данных к работе.

    Что принимает:
    - ничего.

    Что возвращает:
    - ничего.
    """

    await init_database()
    await migrate_ui_texts_table()
    await seed_games()
    await seed_prompts()
    await seed_ui_texts()
