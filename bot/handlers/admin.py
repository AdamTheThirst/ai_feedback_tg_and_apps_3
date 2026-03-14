# bot/handlers/admin.py

"""
Обработчики административного раздела.

Отвечают за:
- вход в админку по паролю;
- допуск в админку только для конкретного user_id;
- вход в гостевой режим по специальному паролю;
- фиксацию инцидентов несанкционированного входа;
- показ главного меню админки;
- показ раздела работы с промтами и играми;
- показ раздела аналитики;
- редактирование приветствия стартового экрана;
- редактирование приветствия админки;
- редактирование текстов кнопок;
- смену пароля администратора;
- добавление новой игры;
- добавление нового аналитического промта;
- удаление игры;
- выход из админки.

Как работает:
- использует FSM для пошаговых сценариев;
- получает и обновляет данные через репозитории;
- использует inline-клавиатуры;
- в гостевом режиме даёт просматривать админку, но не сохраняет изменения.

Что принимает:
- сообщения Telegram;
- callback-запросы Telegram;
- FSMContext;
- сессию базы данных.

Что возвращает:
- ничего.
"""

from contextlib import suppress
from html import escape
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.start import send_start_screen
from bot.keyboards.admin_keyboards import (
    build_admin_analytics_keyboard,
    build_admin_main_keyboard,
    build_admin_tools_keyboard,
    build_buttons_list_keyboard,
    build_confirm_keyboard,
    build_games_selection_keyboard,
    build_post_create_analytics_keyboard,
)
from bot.states.admin import AdminStates
from database.repositories.admin_login_incident_repository import (
    AdminLoginIncidentRepository,
)
from database.repositories.analytics_prompt_repository import AnalyticsPromptRepository
from database.repositories.deleted_prompt_repository import DeletedPromptRepository
from database.repositories.dialog_message_repository import DialogMessageRepository
from database.repositories.game_prompt_repository import GamePromptRepository
from database.repositories.game_repository import GameRepository
from database.repositories.password_repository import PasswordRepository
from database.repositories.ui_text_repository import UITextRepository
from services.analytics_ai import generate_analytics_metadata
from services.security import hash_password, verify_password

router = Router(name="admin-router")
logger = logging.getLogger(__name__)

ADMIN_USER_ID = 467116941
GUEST_ADMIN_PASSWORD = "111111"
GUEST_ADMIN_GREETING = "Это гостевой сеанс. Доступен просмотр, не доступны изменения"
GUEST_ADMIN_SAVE_BLOCK_MESSAGE = "Гостевой режим: изменения не сохранены."


async def is_guest_admin_session(state: FSMContext) -> bool:
    """
    Проверяет, находится ли пользователь в гостевом сеансе админки.

    Что принимает:
    - state: объект FSMContext.

    Что возвращает:
    - True, если это гостевой сеанс;
    - False в остальных случаях.
    """

    data = await state.get_data()
    return bool(data.get("is_guest_admin", False))


async def send_admin_main_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Отправляет пользователю главное меню админки.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.set_state(AdminStates.main_menu)

    ui_repo = UITextRepository(session)
    aliases = [
        "admin_greeting",
        "admin_button_edit_start_greeting",
        "admin_button_edit_admin_greeting",
        "admin_button_edit_buttons",
        "admin_button_change_password",
        "admin_button_prompt_games_work",
        "admin_button_analytics",
        "admin_button_exit",
    ]
    texts = await ui_repo.get_many_by_aliases(aliases)

    guest_mode = await is_guest_admin_session(state)

    greeting_text = texts["admin_greeting"].value
    if guest_mode:
        greeting_text = GUEST_ADMIN_GREETING

    keyboard = build_admin_main_keyboard(
        {
            "admin_button_edit_start_greeting": texts["admin_button_edit_start_greeting"].value,
            "admin_button_edit_admin_greeting": texts["admin_button_edit_admin_greeting"].value,
            "admin_button_edit_buttons": texts["admin_button_edit_buttons"].value,
            "admin_button_change_password": texts["admin_button_change_password"].value,
            "admin_button_prompt_games_work": texts["admin_button_prompt_games_work"].value,
            "admin_button_analytics": texts["admin_button_analytics"].value,
            "admin_button_exit": texts["admin_button_exit"].value,
        }
    )

    await message.answer(escape(greeting_text), reply_markup=keyboard)


async def send_admin_tools_menu(
    message: Message,
    session: AsyncSession,
) -> None:
    """
    Отправляет пользователю раздел работы с промтами и играми.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    ui_repo = UITextRepository(session)
    aliases = [
        "admin_button_tools_add_game",
        "admin_button_tools_add_prompt",
        "admin_button_tools_edit_prompts",
        "admin_button_tools_toggle_prompt",
        "admin_button_tools_delete_prompt",
        "admin_button_tools_delete_game",
        "admin_button_tools_back",
    ]
    texts = await ui_repo.get_many_by_aliases(aliases)

    keyboard = build_admin_tools_keyboard(
        {
            "admin_button_tools_add_game": texts["admin_button_tools_add_game"].value,
            "admin_button_tools_add_prompt": texts["admin_button_tools_add_prompt"].value,
            "admin_button_tools_edit_prompts": texts["admin_button_tools_edit_prompts"].value,
            "admin_button_tools_toggle_prompt": texts["admin_button_tools_toggle_prompt"].value,
            "admin_button_tools_delete_prompt": texts["admin_button_tools_delete_prompt"].value,
            "admin_button_tools_delete_game": texts["admin_button_tools_delete_game"].value,
            "admin_button_tools_back": texts["admin_button_tools_back"].value,
        }
    )

    await message.answer("Работа с промтами и играми", reply_markup=keyboard)


async def send_admin_analytics_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Отправляет пользователю раздел аналитики.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.set_state(AdminStates.analytics_menu)

    ui_repo = UITextRepository(session)
    aliases = [
        "admin_button_analytics_new",
        "admin_button_analytics_edit",
        "admin_button_analytics_delete",
        "admin_button_analytics_back",
    ]
    texts = await ui_repo.get_many_by_aliases(aliases)

    keyboard = build_admin_analytics_keyboard(
        {
            "admin_button_analytics_new": texts["admin_button_analytics_new"].value,
            "admin_button_analytics_edit": texts["admin_button_analytics_edit"].value,
            "admin_button_analytics_delete": texts["admin_button_analytics_delete"].value,
            "admin_button_analytics_back": texts["admin_button_analytics_back"].value,
        }
    )

    await message.answer("Анализ", reply_markup=keyboard)


async def send_text_preview_screen(
    message: Message,
    session: AsyncSession,
    text_alias: str,
    edit_callback: str,
) -> None:
    """
    Показывает текущий текст и кнопки "Изменить" / "Отмена".

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - session: активная сессия базы данных;
    - text_alias: alias текста, который будет редактироваться;
    - edit_callback: callback_data для кнопки "Изменить".

    Что возвращает:
    - ничего.
    """

    ui_repo = UITextRepository(session)
    current_text = await ui_repo.get_by_alias(text_alias)
    common_texts = await ui_repo.get_many_by_aliases(
        ["common_edit_button", "common_cancel_button"]
    )

    text_value = current_text.value if current_text is not None else "Текст не найден"
    keyboard = build_confirm_keyboard(
        edit_text=common_texts["common_edit_button"].value,
        cancel_text=common_texts["common_cancel_button"].value,
        edit_callback=edit_callback,
    )

    await message.answer(
        f"Текущий текст:\n{escape(text_value)}",
        reply_markup=keyboard,
    )


async def register_unauthorized_admin_attempt(
    message: Message,
    session: AsyncSession,
) -> None:
    """
    Фиксирует инцидент несанкционированного входа в админку.

    Что принимает:
    - message: входящее сообщение Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    if message.from_user is None:
        return

    incident_repo = AdminLoginIncidentRepository(session)
    device = None

    await incident_repo.create_incident(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        device=device,
    )

    logger.warning(
        "Несанкционированная попытка входа в админку. user_id=%s username=%s",
        message.from_user.id,
        message.from_user.username,
    )


def sanitize_alias(raw_alias: str) -> str:
    """
    Приводит alias к безопасному формату.

    Что принимает:
    - raw_alias: алиас от ИИ.

    Что возвращает:
    - безопасный alias.
    """

    alias = raw_alias.lower().strip()
    alias = re.sub(r"[^a-z0-9_]+", "_", alias)
    alias = re.sub(r"_+", "_", alias).strip("_")

    if not alias:
        return "analytics_prompt"

    return alias[:80]


async def generate_unique_analytics_alias(
    repo: AnalyticsPromptRepository,
    raw_alias: str,
) -> str:
    """
    Генерирует уникальный alias аналитического промта.

    Что принимает:
    - repo: репозиторий аналитических промтов;
    - raw_alias: сырой alias от ИИ.

    Что возвращает:
    - уникальный alias аналитики.
    """

    base_alias = sanitize_alias(raw_alias)
    alias = base_alias
    counter = 2

    while await repo.get_by_alias(alias) is not None:
        alias = f"{base_alias}_{counter}"
        counter += 1

    return alias


async def finalize_new_analytics_creation(
    target_message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Завершает сценарий создания нового аналитического промта.

    Что принимает:
    - target_message: сообщение, через которое отправляется ответ;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    data = await state.get_data()
    guest_mode = await is_guest_admin_session(state)

    game_id = data.get("analytics_game_id")
    game_name = data.get("analytics_game_name")
    prompt_text = data.get("analytics_prompt_text")

    if not game_id or not game_name or not prompt_text:
        await target_message.answer("Не удалось собрать данные для аналитики.")
        await send_admin_analytics_menu(target_message, state, session)
        return

    wait_message = await target_message.answer("Подготовка и запись")

    if guest_mode:
        with suppress(Exception):
            await wait_message.delete()

        await target_message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_analytics_menu(target_message, state, session)
        return

    repo = AnalyticsPromptRepository(session)
    metadata = await generate_analytics_metadata(prompt_text)
    unique_alias = await generate_unique_analytics_alias(repo, metadata.alias)

    await repo.create(
        game=game_id,
        header=metadata.header,
        alias=unique_alias,
        comment=metadata.comment,
        promt=prompt_text,
    )

    with suppress(Exception):
        await wait_message.delete()

    ui_repo = UITextRepository(session)
    texts = await ui_repo.get_many_by_aliases(
        [
            "admin_button_analytics_add_one_more",
            "admin_button_analytics_back",
        ]
    )

    keyboard = build_post_create_analytics_keyboard(
        add_more_text=texts["admin_button_analytics_add_one_more"].value,
        back_text=texts["admin_button_analytics_back"].value,
    )

    await state.set_state(AdminStates.analytics_menu)
    await state.update_data(
        last_analytics_game_id=game_id,
        last_analytics_game_name=game_name,
        analytics_prompt_text=None,
    )

    await target_message.answer(
        f"Записано.\n"
        f"Игра: {escape(game_name)}\n"
        f"Header: {escape(metadata.header)}\n"
        f"Comment: {escape(metadata.comment)}\n"
        f"Alias: {escape(unique_alias)}",
        reply_markup=keyboard,
    )


@router.message(Command("admin"))
async def admin_command_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает команду /admin.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.clear()

    password_repo = PasswordRepository(session)
    await password_repo.get_or_create(
        user_id=ADMIN_USER_ID,
        default_password_hash=hash_password("123"),
    )

    logger.info(
        "Запрошен вход в админку. user_id=%s",
        message.from_user.id if message.from_user else None,
    )

    await state.set_state(AdminStates.waiting_password)
    await message.answer("Введите пароль администратора:")


@router.message(AdminStates.waiting_password)
async def admin_password_input_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод пароля для входа в админку.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    raw_password = (message.text or "").strip()

    if raw_password == GUEST_ADMIN_PASSWORD:
        await state.update_data(is_guest_admin=True)

        logger.info(
            "Успешный вход в гостевой режим админки. user_id=%s",
            message.from_user.id,
        )

        await send_admin_main_menu(message, state, session)
        return

    password_repo = PasswordRepository(session)
    admin_password_row = await password_repo.get_by_user_id(ADMIN_USER_ID)

    if admin_password_row is None:
        await message.answer("Пароль администратора не найден.")
        await send_start_screen(message, state, session)
        return

    is_password_valid = verify_password(raw_password, admin_password_row.admin)

    if not is_password_valid:
        logger.warning(
            "Неверный пароль админки. user_id=%s",
            message.from_user.id,
        )
        await message.answer("Неверный пароль. Возврат на стартовый экран.")
        await send_start_screen(message, state, session)
        return

    if message.from_user.id != ADMIN_USER_ID:
        await register_unauthorized_admin_attempt(message, session)
        await message.answer("Доступ запрещён. Попытка зафиксирована.")
        await send_start_screen(message, state, session)
        return

    await state.update_data(is_guest_admin=False)

    logger.info(
        "Успешный вход администратора. user_id=%s",
        message.from_user.id,
    )

    await send_admin_main_menu(message, state, session)


@router.callback_query(F.data == "admin:tools_menu")
async def admin_tools_menu_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Открывает раздел работы с промтами и играми.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_admin_tools_menu(callback.message, session)


@router.callback_query(F.data == "admin:analytics_menu")
async def admin_analytics_menu_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Открывает раздел аналитики.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_admin_analytics_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:new_analytics")
async def admin_new_analytics_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий создания новой аналитики.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    games = await GameRepository(session).list_all()

    if not games:
        await callback.message.answer("Список игр пуст. Сначала добавьте игру.")
        return

    await state.set_state(AdminStates.waiting_new_analytics_game)

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_games_selection_keyboard(
        games=games,
        cancel_text=common_texts["common_cancel_button"].value,
        callback_prefix="admin:new_analytics_select_game",
        cancel_callback="admin:analytics_menu",
    )

    await callback.message.answer(
        "Для какой игры добавить аналитику?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("admin:new_analytics_select_game:"))
async def admin_new_analytics_select_game_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор игры для новой аналитики.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    game_id = callback.data.split("admin:new_analytics_select_game:", maxsplit=1)[1]
    game = await GameRepository(session).get_by_game_id(game_id)

    if game is None:
        await callback.message.answer("Игра не найдена.")
        return

    await state.update_data(
        analytics_game_id=game.game_id,
        analytics_game_name=game.name,
        last_analytics_game_id=game.game_id,
        last_analytics_game_name=game.name,
    )
    await state.set_state(AdminStates.waiting_new_analytics_prompt)
    await callback.message.answer("Введите аналитический промт:")


@router.message(AdminStates.waiting_new_analytics_prompt)
async def admin_new_analytics_prompt_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод текста новой аналитики.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    prompt_text = (message.text or "").strip()

    if len(prompt_text) < 10:
        await message.answer("Промт слишком короткий.")
        return

    await state.update_data(analytics_prompt_text=prompt_text)
    await finalize_new_analytics_creation(message, state, session)


@router.callback_query(F.data == "admin:analytics_add_one_more")
async def admin_analytics_add_one_more_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Запускает ввод ещё одного аналитического промта для последней выбранной игры.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    game_id = data.get("last_analytics_game_id")
    game_name = data.get("last_analytics_game_name")

    if not game_id or not game_name:
        await callback.message.answer("Не удалось определить игру. Выберите её заново.")
        return

    await state.update_data(
        analytics_game_id=game_id,
        analytics_game_name=game_name,
    )
    await state.set_state(AdminStates.waiting_new_analytics_prompt)
    await callback.message.answer(
        f"Введите ещё один аналитический промт для игры {escape(game_name)}:"
    )


@router.callback_query(F.data == "admin:edit_analytics")
async def admin_edit_analytics_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает нажатие на кнопку "Изменить аналитику".

    Пока это заготовка для следующего шага.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.analytics_menu)

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("ЭТО ЗАГЛУШКА. Изменение аналитики сделаем следующим шагом.")
    await send_admin_analytics_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:delete_analytics")
async def admin_delete_analytics_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает нажатие на кнопку "Удалить аналитику".

    Пока это заготовка для следующего шага.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.analytics_menu)

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("ЭТО ЗАГЛУШКА. Удаление аналитики сделаем следующим шагом.")
    await send_admin_analytics_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:add_game")
async def admin_add_game_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Запускает сценарий добавления новой игры.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_new_game_name)
    await callback.message.answer("Введите название новой игры:")


@router.message(AdminStates.waiting_new_game_name)
async def admin_add_game_name_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод названия новой игры.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    game_name = (message.text or "").strip()
    guest_mode = await is_guest_admin_session(state)

    if len(game_name) < 2:
        await message.answer("Название слишком короткое. Возвращаю в раздел.")
        await send_admin_tools_menu(message, session)
        return

    if guest_mode:
        logger.info(
            "Гость попытался добавить игру. user_id=%s game_name=%s",
            message.from_user.id if message.from_user else None,
            game_name,
        )
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(message, session)
        return

    game_repo = GameRepository(session)
    new_game = await game_repo.create(game_name)

    ui_repo = UITextRepository(session)
    await ui_repo.create_if_missing(
        alias=f"{new_game.game_id}_greeting",
        value=f"Основное приветствие {new_game.name}",
        text_type="text",
        description=f"Приветствие меню игры {new_game.name}",
        game=new_game.game_id,
        level=None,
        order=None,
        game_alias=None,
    )

    logger.info(
        "Создана новая игра. game_id=%s name=%s user_id=%s",
        new_game.game_id,
        new_game.name,
        message.from_user.id if message.from_user else None,
    )

    await message.answer(
        f"Игра добавлена.\n"
        f"name: {escape(new_game.name)}\n"
        f"game_id: {escape(new_game.game_id)}"
    )
    await send_admin_tools_menu(message, session)


@router.callback_query(F.data == "admin:delete_game")
async def admin_delete_game_start_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий удаления игры.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    game_repo = GameRepository(session)
    games = await game_repo.list_all()

    if not games:
        await callback.message.answer("Список игр пуст.")
        return

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_games_selection_keyboard(
        games=games,
        cancel_text=common_texts["common_cancel_button"].value,
        callback_prefix="admin:delete_game_select",
    )

    await callback.message.answer(
        "Выберите игру, которую хотите удалить:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:edit_start_greeting")
async def admin_preview_start_greeting_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Показывает текущее приветствие стартового экрана.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_text_preview_screen(
        message=callback.message,
        session=session,
        text_alias="start_greeting",
        edit_callback="admin:confirm_edit_start_greeting",
    )


@router.callback_query(F.data == "admin:edit_admin_greeting")
async def admin_preview_admin_greeting_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Показывает текущее приветствие админки.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_text_preview_screen(
        message=callback.message,
        session=session,
        text_alias="admin_greeting",
        edit_callback="admin:confirm_edit_admin_greeting",
    )


@router.callback_query(F.data == "admin:confirm_edit_start_greeting")
async def admin_confirm_edit_start_greeting_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние ожидания нового текста стартового приветствия.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_new_start_greeting)
    await callback.message.answer("Напишите новый текст")


@router.callback_query(F.data == "admin:confirm_edit_admin_greeting")
async def admin_confirm_edit_admin_greeting_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние ожидания нового текста приветствия админки.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_new_admin_greeting)
    await callback.message.answer("Напишите новый текст")


@router.message(AdminStates.waiting_new_start_greeting)
async def admin_new_start_greeting_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст для стартового приветствия.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()
    guest_mode = await is_guest_admin_session(state)

    if len(new_text) >= 10:
        if guest_mode:
            logger.info(
                "Гость попытался изменить стартовое приветствие. user_id=%s",
                message.from_user.id if message.from_user else None,
            )
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            ui_repo = UITextRepository(session)
            await ui_repo.update_value("start_greeting", new_text)
            await message.answer("Текст обновлён.")
    else:
        await message.answer("Текст слишком короткий. Возвращаю в админку.")

    await send_admin_main_menu(message, state, session)


@router.message(AdminStates.waiting_new_admin_greeting)
async def admin_new_admin_greeting_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст для приветствия админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()
    guest_mode = await is_guest_admin_session(state)

    if len(new_text) >= 10:
        if guest_mode:
            logger.info(
                "Гость попытался изменить приветствие админки. user_id=%s",
                message.from_user.id if message.from_user else None,
            )
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            ui_repo = UITextRepository(session)
            await ui_repo.update_value("admin_greeting", new_text)
            await message.answer("Текст обновлён.")
    else:
        await message.answer("Текст слишком короткий. Возвращаю в админку.")

    await send_admin_main_menu(message, state, session)


@router.callback_query(F.data == "admin:edit_buttons")
async def admin_edit_buttons_list_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Показывает список всех кнопок системы для редактирования.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    ui_repo = UITextRepository(session)
    buttons = await ui_repo.get_all_buttons()
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_buttons_list_keyboard(
        buttons=buttons,
        cancel_text=common_texts["common_cancel_button"].value,
    )

    await callback.message.answer(
        "Выберите кнопку, текст которой хотите изменить:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:change_password")
async def admin_change_password_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Запускает сценарий изменения пароля админки.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_current_password)
    await callback.message.answer("Изменение пароля\n\nВведите текущий пароль:")


@router.callback_query(F.data == "admin:back_main")
async def admin_back_to_main_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Возвращает пользователя в главное меню админки.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.main_menu)
    await send_admin_main_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:exit")
async def admin_exit_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Выводит пользователя из админки.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_start_screen(callback.message, state, session)
