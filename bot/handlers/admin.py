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
- удаление игры;
- добавление нового игрового промта;
- изменение игрового промта;
- активацию/деактивацию игрового промта;
- удаление игрового промта;
- добавление нового аналитического промта;
- изменение аналитического промта;
- удаление аналитического промта;
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
- сессию базы данных;
- bot для сохранения фотографий.

Что возвращает:
- ничего.
"""

from contextlib import suppress
from html import escape
import logging
import re

from aiogram import Bot, F, Router
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
    build_prompt_edit_actions_keyboard,
    build_prompt_selection_keyboard,
    build_skip_image_keyboard,
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
from services.analytics_ai import (
    generate_analytics_metadata,
    generate_edited_analytics_metadata,
)
from services.images import save_telegram_photo
from services.security import hash_password, verify_password
from services.translit import slugify_text

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
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Отправляет пользователю раздел работы с промтами и играми.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.set_state(AdminStates.tools_menu)

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


async def generate_unique_prompt_alias(
    prompt_repo: GamePromptRepository,
    button_name: str,
) -> str:
    """
    Генерирует уникальный alias игрового промта.

    Как работает:
    - берёт название кнопки;
    - транслитерирует его;
    - добавляет префикс game_alias_;
    - если alias уже занят, добавляет числовой суффикс.

    Что принимает:
    - prompt_repo: репозиторий промтов;
    - button_name: название кнопки сценария.

    Что возвращает:
    - уникальный alias игрового промта.
    """

    slug = slugify_text(button_name)
    base_alias = f"game_alias_{slug}"
    alias = base_alias
    counter = 2

    while await prompt_repo.get_by_alias(alias) is not None:
        alias = f"{base_alias}_{counter}"
        counter += 1

    return alias


async def generate_unique_prompt_button_alias(
    ui_repo: UITextRepository,
    game_id: str,
    button_name: str,
) -> str:
    """
    Генерирует уникальный alias кнопки второго уровня для игрового промта.

    Что принимает:
    - ui_repo: репозиторий ui_texts;
    - game_id: системный game_id;
    - button_name: название кнопки.

    Что возвращает:
    - уникальный alias кнопки.
    """

    slug = slugify_text(button_name)
    base_alias = f"btn_second_level_{game_id}_{slug}"
    alias = base_alias
    counter = 2

    while await ui_repo.get_by_alias(alias) is not None:
        alias = f"{base_alias}_{counter}"
        counter += 1

    return alias


async def build_prompt_items(
    session: AsyncSession,
    with_status: bool = False,
) -> list[tuple[str, str]]:
    """
    Собирает список игровых промтов для вывода в кнопках.

    Как работает:
    - берёт кнопки второго уровня из ui_texts;
    - для каждой кнопки ищет связанный промт по game_alias;
    - при необходимости добавляет статус активности.

    Что принимает:
    - session: активная сессия БД;
    - with_status: нужно ли добавлять статус активности.

    Что возвращает:
    - список кортежей (текст кнопки, game_alias).
    """

    ui_repo = UITextRepository(session)
    prompt_repo = GamePromptRepository(session)
    game_repo = GameRepository(session)

    prompt_buttons = await ui_repo.list_prompt_buttons()
    items: list[tuple[str, str]] = []

    for button in prompt_buttons:
        if not button.game_alias:
            continue

        prompt = await prompt_repo.get_by_alias(button.game_alias)
        if prompt is None:
            continue

        game_name = button.game or ""
        game = await game_repo.get_by_game_id(game_name) if game_name else None
        game_title = game.name if game is not None else button.game or "Без игры"

        text = f"{game_title} | {button.value}"

        if with_status:
            status = "(А)" if prompt.is_active else "(U)"
            text = f"{text} {status}"

        items.append((text, button.game_alias))

    return items


async def send_prompt_selection_menu(
    message: Message,
    session: AsyncSession,
    callback_prefix: str,
    empty_text: str,
    with_status: bool = False,
) -> None:
    """
    Отправляет пользователю список игровых промтов.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - session: активная сессия БД;
    - callback_prefix: префикс callback_data;
    - empty_text: сообщение, если список пуст;
    - with_status: показывать ли статус активности.

    Что возвращает:
    - ничего.
    """

    items = await build_prompt_items(session=session, with_status=with_status)

    if not items:
        await message.answer(empty_text)
        return

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_prompt_selection_keyboard(
        items=items,
        cancel_text=common_texts["common_cancel_button"].value,
        callback_prefix=callback_prefix,
        cancel_callback="admin:tools_menu",
    )

    await message.answer("Выберите промт:", reply_markup=keyboard)


async def build_analytics_items(
    session: AsyncSession,
) -> list[tuple[str, str]]:
    """
    Собирает список аналитических промтов для вывода в кнопках.

    Что принимает:
    - session: активная сессия базы данных.

    Что возвращает:
    - список кортежей в формате (текст_кнопки, alias).
    """

    repo = AnalyticsPromptRepository(session)
    analytics_rows = await repo.list_all()
    items: list[tuple[str, str]] = []

    for item in analytics_rows:
        button_text = f"{item.comment} | {item.header}"
        items.append((button_text, item.alias))

    return items


async def send_analytics_selection_menu(
    message: Message,
    session: AsyncSession,
    callback_prefix: str,
) -> None:
    """
    Отправляет пользователю список аналитических промтов.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - session: активная сессия базы данных;
    - callback_prefix: префикс callback_data.

    Что возвращает:
    - ничего.
    """

    items = await build_analytics_items(session)

    if not items:
        await message.answer("Список аналитики пуст.")
        return

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_prompt_selection_keyboard(
        items=items,
        cancel_text=common_texts["common_cancel_button"].value,
        callback_prefix=callback_prefix,
        cancel_callback="admin:analytics_menu",
    )

    await message.answer("Выберите аналитический промт:", reply_markup=keyboard)


async def send_prompt_actions_menu(
    message: Message,
    session: AsyncSession,
) -> None:
    """
    Отправляет меню действий для выбранного игрового промта.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - session: активная сессия БД.

    Что возвращает:
    - ничего.
    """

    ui_repo = UITextRepository(session)
    texts = await ui_repo.get_many_by_aliases(
        [
            "admin_button_prompt_action_name",
            "admin_button_prompt_action_conditions",
            "admin_button_prompt_action_prompt",
            "admin_button_prompt_action_image",
            "common_cancel_button",
        ]
    )

    keyboard = build_prompt_edit_actions_keyboard(
        {
            "admin_button_prompt_action_name": texts["admin_button_prompt_action_name"].value,
            "admin_button_prompt_action_conditions": texts["admin_button_prompt_action_conditions"].value,
            "admin_button_prompt_action_prompt": texts["admin_button_prompt_action_prompt"].value,
            "admin_button_prompt_action_image": texts["admin_button_prompt_action_image"].value,
            "common_cancel_button": texts["common_cancel_button"].value,
        }
    )

    await message.answer("Выберите, что хотите изменить:", reply_markup=keyboard)


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


async def finalize_edit_analytics(
    target_message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Завершает сценарий изменения аналитического промта.

    Что принимает:
    - target_message: сообщение, через которое отправляется ответ;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    data = await state.get_data()
    guest_mode = await is_guest_admin_session(state)

    analytics_alias = data.get("edit_analytics_alias")
    new_prompt_text = data.get("edit_analytics_prompt_text")

    if not analytics_alias or not new_prompt_text:
        await target_message.answer("Не удалось собрать данные для изменения аналитики.")
        await send_admin_analytics_menu(target_message, state, session)
        return

    row = await AnalyticsPromptRepository(session).get_by_alias(analytics_alias)

    if row is None:
        await target_message.answer("Аналитический промт не найден.")
        await send_admin_analytics_menu(target_message, state, session)
        return

    wait_message = await target_message.answer("Подготовка и запись")

    if guest_mode:
        with suppress(Exception):
            await wait_message.delete()

        await target_message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_analytics_menu(target_message, state, session)
        return

    metadata = await generate_edited_analytics_metadata(new_prompt_text)

    await AnalyticsPromptRepository(session).update_prompt(
        alias=analytics_alias,
        header=metadata.header,
        comment=metadata.comment,
        promt=new_prompt_text,
    )

    with suppress(Exception):
        await wait_message.delete()

    await target_message.answer("Аналитический промт обновлён.")
    await send_admin_analytics_menu(target_message, state, session)


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
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Открывает раздел работы с промтами и играми.

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

    await send_admin_tools_menu(callback.message, state, session)


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
        await send_admin_tools_menu(message, state, session)
        return

    if guest_mode:
        logger.info(
            "Гость попытался добавить игру. user_id=%s game_name=%s",
            message.from_user.id if message.from_user else None,
            game_name,
        )
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(message, state, session)
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
    await send_admin_tools_menu(message, state, session)


@router.callback_query(F.data == "admin:delete_game")
async def admin_delete_game_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий удаления игры.

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

    game_repo = GameRepository(session)
    games = await game_repo.list_all()

    if not games:
        await callback.message.answer("Список игр пуст.")
        return

    await state.set_state(AdminStates.waiting_delete_game_select)

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_games_selection_keyboard(
        games=games,
        cancel_text=common_texts["common_cancel_button"].value,
        callback_prefix="admin:delete_game_select",
        cancel_callback="admin:tools_menu",
    )

    await callback.message.answer(
        "Выберите игру, которую хотите удалить:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("admin:delete_game_select:"))
async def admin_delete_game_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор игры для удаления.

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

    game_id = callback.data.split("admin:delete_game_select:", maxsplit=1)[1]
    game = await GameRepository(session).get_by_game_id(game_id)

    if game is None:
        await callback.message.answer("Игра не найдена.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    await state.update_data(delete_game_id=game.game_id, delete_game_name=game.name)
    await state.set_state(AdminStates.waiting_delete_game_confirm)

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(
        ["common_delete_button", "common_cancel_button"]
    )

    keyboard = build_confirm_keyboard(
        edit_text=common_texts["common_delete_button"].value,
        cancel_text=common_texts["common_cancel_button"].value,
        edit_callback="admin:confirm_delete_game",
        cancel_callback="admin:tools_menu",
    )

    await callback.message.answer(
        f"Вы точно хотите удалить игру {escape(game.name)}?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:confirm_delete_game")
async def admin_confirm_delete_game_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Подтверждает удаление игры и всех связанных с ней записей.

    Как работает:
    - переносит игровые промты в deleted_prompts;
    - переносит аналитические промты этой игры в deleted_prompts;
    - удаляет связанные данные из game_prompts, ui_texts, dialog_messages, analytics_prompts;
    - удаляет саму игру.

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

    data = await state.get_data()
    game_id = data.get("delete_game_id")
    game_name = data.get("delete_game_name")

    if not game_id or not game_name:
        await callback.message.answer("Не удалось определить игру для удаления.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    if await is_guest_admin_session(state):
        await callback.message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(callback.message, state, session)
        return

    game_repo = GameRepository(session)
    prompt_repo = GamePromptRepository(session)
    analytics_repo = AnalyticsPromptRepository(session)
    ui_repo = UITextRepository(session)
    dialog_repo = DialogMessageRepository(session)
    deleted_repo = DeletedPromptRepository(session)

    game_prompts = await prompt_repo.list_by_game_id(game_id)
    for item in game_prompts:
        await deleted_repo.create(game_name=game_name, promt=item.prompt_text)

    analytics_prompts = await analytics_repo.list_by_game(game_id)
    for item in analytics_prompts:
        await deleted_repo.create(game_name=game_name, promt=item.promt)

    await analytics_repo.delete_by_game(game_id)
    await dialog_repo.delete_by_game_id(game_id)
    await ui_repo.delete_by_game_id(game_id)
    await prompt_repo.delete_by_game_id(game_id)
    await game_repo.delete_by_game_id(game_id)

    await callback.message.answer(f"Игра {escape(game_name)} удалена.")
    await send_admin_tools_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:add_prompt")
async def admin_add_prompt_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий добавления нового игрового промта.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия БД.

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

    await state.set_state(AdminStates.waiting_add_prompt_select_game)

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_games_selection_keyboard(
        games=games,
        cancel_text=common_texts["common_cancel_button"].value,
        callback_prefix="admin:add_prompt_select_game",
        cancel_callback="admin:tools_menu",
    )

    await callback.message.answer(
        "Выберите игру, для которой нужно добавить промт:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("admin:add_prompt_select_game:"))
async def admin_add_prompt_select_game_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор игры для добавления нового промта.

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

    game_id = callback.data.split("admin:add_prompt_select_game:", maxsplit=1)[1]
    game = await GameRepository(session).get_by_game_id(game_id)

    if game is None:
        await callback.message.answer("Игра не найдена.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    await state.update_data(
        add_prompt_game_id=game.game_id,
        add_prompt_game_name=game.name,
    )
    await state.set_state(AdminStates.waiting_new_prompt_button_name)
    await callback.message.answer("Введите название для кнопки:")


@router.message(AdminStates.waiting_new_prompt_button_name)
async def admin_add_prompt_button_name_handler(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает ввод названия кнопки нового игрового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    button_name = (message.text or "").strip()

    if not 2 <= len(button_name) <= 30:
        await message.answer("Название кнопки должно быть от 2 до 30 символов.")
        return

    await state.update_data(add_prompt_button_name=button_name)
    await state.set_state(AdminStates.waiting_new_prompt_conditions)
    await message.answer("Введите условие conditions:")


@router.message(AdminStates.waiting_new_prompt_conditions)
async def admin_add_prompt_conditions_handler(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает ввод conditions нового игрового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    conditions = (message.text or "").strip()

    if len(conditions) < 10:
        await message.answer("Текст условий должен быть не короче 10 символов.")
        return

    await state.update_data(add_prompt_conditions=conditions)
    await state.set_state(AdminStates.waiting_new_prompt_text)
    await message.answer("Введите текст промта:")


@router.message(AdminStates.waiting_new_prompt_text)
async def admin_add_prompt_text_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод текста нового игрового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    prompt_text = (message.text or "").strip()

    if len(prompt_text) < 10:
        await message.answer("Текст промта должен быть не короче 10 символов.")
        return

    await state.update_data(add_prompt_text=prompt_text)
    await state.set_state(AdminStates.waiting_new_prompt_image)

    ui_repo = UITextRepository(session)
    texts = await ui_repo.get_many_by_aliases(
        ["admin_button_skip_image", "common_cancel_button"]
    )

    keyboard = build_skip_image_keyboard(
        skip_text=texts["admin_button_skip_image"].value,
        cancel_text=texts["common_cancel_button"].value,
    )

    await message.answer(
        "Загрузите изображение для промта или нажмите «Пропустить изображение».",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:prompt_skip_image")
async def admin_add_prompt_skip_image_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Завершает создание нового промта без изображения.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия БД.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    data = await state.get_data()

    game_id = data.get("add_prompt_game_id")
    game_name = data.get("add_prompt_game_name")
    button_name = data.get("add_prompt_button_name")
    conditions = data.get("add_prompt_conditions")
    prompt_text = data.get("add_prompt_text")

    if not game_id or not button_name or not conditions or not prompt_text:
        await callback.message.answer("Не удалось собрать данные для нового промта.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    if await is_guest_admin_session(state):
        await callback.message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(callback.message, state, session)
        return

    prompt_repo = GamePromptRepository(session)
    ui_repo = UITextRepository(session)

    prompt_alias = await generate_unique_prompt_alias(
        prompt_repo=prompt_repo,
        button_name=button_name,
    )
    button_alias = await generate_unique_prompt_button_alias(
        ui_repo=ui_repo,
        game_id=game_id,
        button_name=button_name,
    )
    button_order = await ui_repo.get_next_order(game=game_id, level=1)

    await prompt_repo.create(
        game_id=game_id,
        alias=prompt_alias,
        conditions=conditions,
        prompt_text=prompt_text,
        img_path=None,
        img_id=None,
        is_active=True,
    )

    await ui_repo.create_if_missing(
        alias=button_alias,
        value=button_name,
        text_type="button",
        description=f"Кнопка второго уровня сценария {button_name} для игры {game_name}",
        game=game_id,
        level=1,
        order=button_order,
        game_alias=prompt_alias,
    )

    await ui_repo.create_if_missing(
        alias=f"greeting_{prompt_alias}",
        value=f"Это приветствие {button_name}",
        text_type="text",
        description=f"Приветствие игрового сценария {button_name}",
        game=game_id,
        level=None,
        order=None,
        game_alias=prompt_alias,
    )

    await callback.message.answer("Промт успешно добавлен.")
    await send_admin_tools_menu(callback.message, state, session)


@router.message(AdminStates.waiting_new_prompt_image, F.photo)
async def admin_add_prompt_image_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """
    Завершает создание нового промта с изображением.

    Как работает:
    - сохраняет фото в папку imgs;
    - записывает абсолютный путь в img_path;
    - сохраняет Telegram file_id в img_id;
    - создаёт сам промт и связанную кнопку.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных;
    - bot: объект Telegram-бота.

    Что возвращает:
    - ничего.
    """

    data = await state.get_data()

    game_id = data.get("add_prompt_game_id")
    game_name = data.get("add_prompt_game_name")
    button_name = data.get("add_prompt_button_name")
    conditions = data.get("add_prompt_conditions")
    prompt_text = data.get("add_prompt_text")

    if not game_id or not button_name or not conditions or not prompt_text:
        await message.answer("Не удалось собрать данные для нового промта.")
        await send_admin_tools_menu(message, state, session)
        return

    if not message.photo:
        await message.answer("Пожалуйста, отправьте изображение.")
        return

    if await is_guest_admin_session(state):
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(message, state, session)
        return

    prompt_repo = GamePromptRepository(session)
    ui_repo = UITextRepository(session)

    prompt_alias = await generate_unique_prompt_alias(
        prompt_repo=prompt_repo,
        button_name=button_name,
    )
    button_alias = await generate_unique_prompt_button_alias(
        ui_repo=ui_repo,
        game_id=game_id,
        button_name=button_name,
    )
    button_order = await ui_repo.get_next_order(game=game_id, level=1)

    telegram_file_id = message.photo[-1].file_id
    img_path = await save_telegram_photo(
        bot=bot,
        telegram_file_id=telegram_file_id,
        filename_base=prompt_alias,
    )

    await prompt_repo.create(
        game_id=game_id,
        alias=prompt_alias,
        conditions=conditions,
        prompt_text=prompt_text,
        img_path=img_path,
        img_id=telegram_file_id,
        is_active=True,
    )

    await ui_repo.create_if_missing(
        alias=button_alias,
        value=button_name,
        text_type="button",
        description=f"Кнопка второго уровня сценария {button_name} для игры {game_name}",
        game=game_id,
        level=1,
        order=button_order,
        game_alias=prompt_alias,
    )

    await ui_repo.create_if_missing(
        alias=f"greeting_{prompt_alias}",
        value=f"Это приветствие {button_name}",
        text_type="text",
        description=f"Приветствие игрового сценария {button_name}",
        game=game_id,
        level=None,
        order=None,
        game_alias=prompt_alias,
    )

    await message.answer("Промт с изображением успешно добавлен.")
    await send_admin_tools_menu(message, state, session)


@router.message(AdminStates.waiting_new_prompt_image)
async def admin_add_prompt_image_invalid_handler(
    message: Message,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает некорректный ввод на шаге ожидания изображения нового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - session: активная сессия БД.

    Что возвращает:
    - ничего.
    """

    ui_repo = UITextRepository(session)
    texts = await ui_repo.get_many_by_aliases(
        ["admin_button_skip_image", "common_cancel_button"]
    )

    keyboard = build_skip_image_keyboard(
        skip_text=texts["admin_button_skip_image"].value,
        cancel_text=texts["common_cancel_button"].value,
    )

    await message.answer(
        "Нужно отправить изображение или нажать «Пропустить изображение».",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:edit_prompts")
async def admin_edit_prompts_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий изменения игрового промта.

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

    await state.set_state(AdminStates.waiting_edit_prompt_select)
    await send_prompt_selection_menu(
        message=callback.message,
        session=session,
        callback_prefix="admin:edit_prompt_select",
        empty_text="Список промтов пуст.",
        with_status=False,
    )


@router.callback_query(F.data.startswith("admin:edit_prompt_select:"))
async def admin_edit_prompt_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор игрового промта для изменения.

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

    game_alias = callback.data.split("admin:edit_prompt_select:", maxsplit=1)[1]

    prompt = await GamePromptRepository(session).get_by_alias(game_alias)
    button = await UITextRepository(session).get_prompt_button_by_game_alias(game_alias)

    if prompt is None or button is None:
        await callback.message.answer("Промт не найден.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    await state.update_data(
        selected_prompt_alias=game_alias,
        selected_prompt_button_alias=button.alias,
        selected_prompt_button_value=button.value,
    )

    await send_prompt_actions_menu(callback.message, session)


@router.callback_query(F.data == "admin:prompt_action_name")
async def admin_prompt_action_name_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние изменения названия кнопки промта.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_edit_prompt_name)
    await callback.message.answer("Введите новое название кнопки от 2 до 30 символов:")


@router.callback_query(F.data == "admin:prompt_action_conditions")
async def admin_prompt_action_conditions_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние изменения условий промта.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_edit_prompt_conditions)
    await callback.message.answer("Введите новые условия промта:")


@router.callback_query(F.data == "admin:prompt_action_prompt")
async def admin_prompt_action_prompt_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние изменения текста промта.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_edit_prompt_text)
    await callback.message.answer("Введите новый текст промта:")


@router.callback_query(F.data == "admin:prompt_action_image")
async def admin_prompt_action_image_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние изменения изображения промта.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_edit_prompt_image)
    await callback.message.answer("Загрузите новое изображение для промта:")


@router.message(AdminStates.waiting_edit_prompt_name)
async def admin_edit_prompt_name_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает изменение названия кнопки игрового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_value = (message.text or "").strip()

    if not 2 <= len(new_value) <= 30:
        await message.answer("Название должно быть от 2 до 30 символов.")
        return

    data = await state.get_data()
    button_alias = data.get("selected_prompt_button_alias")

    if not button_alias:
        await message.answer("Не удалось определить кнопку промта.")
        await send_admin_tools_menu(message, state, session)
        return

    if await is_guest_admin_session(state):
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(message, state, session)
        return

    await UITextRepository(session).update_value(button_alias, new_value)
    await message.answer("Название кнопки промта обновлено.")
    await send_admin_tools_menu(message, state, session)


@router.message(AdminStates.waiting_edit_prompt_conditions)
async def admin_edit_prompt_conditions_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает изменение условий игрового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_conditions = (message.text or "").strip()

    if len(new_conditions) < 10:
        await message.answer("Текст условий должен быть не короче 10 символов.")
        return

    data = await state.get_data()
    prompt_alias = data.get("selected_prompt_alias")

    if not prompt_alias:
        await message.answer("Не удалось определить промт.")
        await send_admin_tools_menu(message, state, session)
        return

    if await is_guest_admin_session(state):
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(message, state, session)
        return

    await GamePromptRepository(session).update_conditions(prompt_alias, new_conditions)
    await message.answer("Условия промта обновлены.")
    await send_admin_tools_menu(message, state, session)


@router.message(AdminStates.waiting_edit_prompt_text)
async def admin_edit_prompt_text_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает изменение текста игрового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_prompt_text = (message.text or "").strip()

    if len(new_prompt_text) < 10:
        await message.answer("Текст промта должен быть не короче 10 символов.")
        return

    data = await state.get_data()
    prompt_alias = data.get("selected_prompt_alias")

    if not prompt_alias:
        await message.answer("Не удалось определить промт.")
        await send_admin_tools_menu(message, state, session)
        return

    if await is_guest_admin_session(state):
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(message, state, session)
        return

    await GamePromptRepository(session).update_prompt_text(prompt_alias, new_prompt_text)
    await message.answer("Текст промта обновлён.")
    await send_admin_tools_menu(message, state, session)


@router.message(AdminStates.waiting_edit_prompt_image, F.photo)
async def admin_edit_prompt_image_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """
    Обрабатывает изменение изображения игрового промта.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных;
    - bot: объект Telegram-бота.

    Что возвращает:
    - ничего.
    """

    data = await state.get_data()
    prompt_alias = data.get("selected_prompt_alias")

    if not prompt_alias:
        await message.answer("Не удалось определить промт.")
        await send_admin_tools_menu(message, state, session)
        return

    if not message.photo:
        await message.answer("Пожалуйста, отправьте изображение.")
        return

    if await is_guest_admin_session(state):
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(message, state, session)
        return

    telegram_file_id = message.photo[-1].file_id
    img_path = await save_telegram_photo(
        bot=bot,
        telegram_file_id=telegram_file_id,
        filename_base=prompt_alias,
    )

    await GamePromptRepository(session).update_image_data(
        alias=prompt_alias,
        img_path=img_path,
        img_id=telegram_file_id,
    )

    await message.answer("Изображение промта обновлено.")
    await send_admin_tools_menu(message, state, session)


@router.message(AdminStates.waiting_edit_prompt_image)
async def admin_edit_prompt_image_invalid_handler(
    message: Message,
) -> None:
    """
    Обрабатывает некорректный ввод на шаге ожидания нового изображения промта.

    Что принимает:
    - message: входящее сообщение Telegram.

    Что возвращает:
    - ничего.
    """

    await message.answer("Нужно отправить новое изображение для промта.")


@router.callback_query(F.data == "admin:toggle_prompt")
async def admin_toggle_prompt_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий активации/деактивации игрового промта.

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

    await state.set_state(AdminStates.waiting_toggle_prompt_select)
    await send_prompt_selection_menu(
        message=callback.message,
        session=session,
        callback_prefix="admin:toggle_prompt_select",
        empty_text="Список промтов пуст.",
        with_status=True,
    )


@router.callback_query(F.data.startswith("admin:toggle_prompt_select:"))
async def admin_toggle_prompt_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор игрового промта для переключения активности.

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

    prompt_alias = callback.data.split("admin:toggle_prompt_select:", maxsplit=1)[1]

    if await is_guest_admin_session(state):
        await callback.message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(callback.message, state, session)
        return

    new_status = await GamePromptRepository(session).toggle_is_active(prompt_alias)

    if new_status is None:
        await callback.message.answer("Промт не найден.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    status_text = "активирован" if new_status else "деактивирован"
    await callback.message.answer(f"Промт {escape(prompt_alias)} {status_text}.")
    await send_admin_tools_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:delete_prompt")
async def admin_delete_prompt_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий удаления игрового промта.

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

    await state.set_state(AdminStates.waiting_delete_prompt_select)
    await send_prompt_selection_menu(
        message=callback.message,
        session=session,
        callback_prefix="admin:delete_prompt_select",
        empty_text="Список промтов пуст.",
        with_status=False,
    )


@router.callback_query(F.data.startswith("admin:delete_prompt_select:"))
async def admin_delete_prompt_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор игрового промта для удаления.

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

    prompt_alias = callback.data.split("admin:delete_prompt_select:", maxsplit=1)[1]

    prompt = await GamePromptRepository(session).get_by_alias(prompt_alias)
    button = await UITextRepository(session).get_prompt_button_by_game_alias(prompt_alias)

    if prompt is None or button is None:
        await callback.message.answer("Промт не найден.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    await state.update_data(
        delete_prompt_alias=prompt.alias,
        delete_prompt_button_value=button.value,
        delete_prompt_game_id=prompt.game_id,
    )
    await state.set_state(AdminStates.waiting_delete_prompt_confirm)

    ui_repo = UITextRepository(session)
    texts = await ui_repo.get_many_by_aliases(
        ["common_delete_button", "common_cancel_button"]
    )

    keyboard = build_confirm_keyboard(
        edit_text=texts["common_delete_button"].value,
        cancel_text=texts["common_cancel_button"].value,
        edit_callback="admin:confirm_delete_prompt",
        cancel_callback="admin:tools_menu",
    )

    await callback.message.answer(
        f"Вы точно хотите удалить промт {escape(button.value)}?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:confirm_delete_prompt")
async def admin_confirm_delete_prompt_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Подтверждает удаление игрового промта.

    Как работает:
    - переносит текст промта в deleted_prompts;
    - удаляет связанные записи из ui_texts и dialog_messages;
    - удаляет запись из game_prompts.

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

    data = await state.get_data()
    prompt_alias = data.get("delete_prompt_alias")
    game_id = data.get("delete_prompt_game_id")

    if not prompt_alias or not game_id:
        await callback.message.answer("Не удалось определить промт для удаления.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    prompt_repo = GamePromptRepository(session)
    prompt = await prompt_repo.get_by_alias(prompt_alias)

    if prompt is None:
        await callback.message.answer("Промт уже удалён.")
        await send_admin_tools_menu(callback.message, state, session)
        return

    if await is_guest_admin_session(state):
        await callback.message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_tools_menu(callback.message, state, session)
        return

    game = await GameRepository(session).get_by_game_id(game_id)
    game_name = game.name if game is not None else game_id

    await DeletedPromptRepository(session).create(
        game_name=game_name,
        promt=prompt.prompt_text,
    )
    await DialogMessageRepository(session).delete_by_subgame_id(prompt.alias)
    await UITextRepository(session).delete_by_game_alias(prompt.alias)
    await prompt_repo.delete_by_alias(prompt.alias)

    await callback.message.answer("Промт удалён.")
    await send_admin_tools_menu(callback.message, state, session)


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
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            await UITextRepository(session).update_value("start_greeting", new_text)
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
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            await UITextRepository(session).update_value("admin_greeting", new_text)
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


@router.callback_query(F.data.startswith("admin:button_select:"))
async def admin_button_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор кнопки для изменения её текста.

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

    button_alias = callback.data.split("admin:button_select:", maxsplit=1)[1]
    button_item = await UITextRepository(session).get_by_alias(button_alias)

    if button_item is None:
        await callback.message.answer("Кнопка не найдена.")
        await send_admin_main_menu(callback.message, state, session)
        return

    await state.update_data(edit_button_alias=button_alias)
    await state.set_state(AdminStates.waiting_new_button_text)
    await callback.message.answer("Введите новый текст, от 2 до 30 символов")


@router.message(AdminStates.waiting_new_button_text)
async def admin_new_button_text_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст для произвольной кнопки системы.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_value = (message.text or "").strip()
    data = await state.get_data()
    button_alias = data.get("edit_button_alias")

    if not button_alias:
        await message.answer("Не удалось определить кнопку.")
        await send_admin_main_menu(message, state, session)
        return

    if not 2 <= len(new_value) <= 30:
        await message.answer("Длина текста должна быть от 2 до 30 символов.")
        await send_admin_main_menu(message, state, session)
        return

    if await is_guest_admin_session(state):
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_main_menu(message, state, session)
        return

    await UITextRepository(session).update_value(button_alias, new_value)
    await message.answer("Текст кнопки обновлён.")
    await send_admin_main_menu(message, state, session)


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


@router.message(AdminStates.waiting_current_password)
async def admin_change_password_current_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод текущего пароля при смене пароля админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    if await is_guest_admin_session(state):
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_main_menu(message, state, session)
        return

    password_row = await PasswordRepository(session).get_by_user_id(ADMIN_USER_ID)

    if password_row is None:
        await message.answer("Пароль администратора не найден.")
        await send_start_screen(message, state, session)
        return

    current_password = (message.text or "").strip()

    if not verify_password(current_password, password_row.admin):
        await message.answer("Текущий пароль неверный. Возврат на стартовый экран.")
        await send_start_screen(message, state, session)
        return

    await state.set_state(AdminStates.waiting_new_password)
    await message.answer("Введите новый пароль:")


@router.message(AdminStates.waiting_new_password)
async def admin_change_password_new_handler(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает ввод нового пароля админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    new_password = (message.text or "").strip()

    if len(new_password) < 3:
        await message.answer("Пароль слишком короткий. Введите новый пароль ещё раз.")
        return

    await state.update_data(new_admin_password=new_password)
    await state.set_state(AdminStates.waiting_new_password_confirm)
    await message.answer("Повторите новый пароль:")


@router.message(AdminStates.waiting_new_password_confirm)
async def admin_change_password_confirm_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает подтверждение нового пароля админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    data = await state.get_data()
    first_password = data.get("new_admin_password")
    second_password = (message.text or "").strip()

    if not first_password or first_password != second_password:
        await message.answer("Пароли не совпали. Возврат в админку.")
        await send_admin_main_menu(message, state, session)
        return

    await PasswordRepository(session).update_password_hash(
        user_id=ADMIN_USER_ID,
        new_password_hash=hash_password(second_password),
    )

    await message.answer("Пароль админки обновлён.")
    await send_admin_main_menu(message, state, session)


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
    Запускает сценарий изменения аналитики.

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

    await state.set_state(AdminStates.waiting_edit_analytics_select)
    await send_analytics_selection_menu(
        message=callback.message,
        session=session,
        callback_prefix="admin:edit_analytics_select",
    )


@router.callback_query(F.data.startswith("admin:edit_analytics_select:"))
async def admin_edit_analytics_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор аналитического промта для изменения.

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

    analytics_alias = callback.data.split("admin:edit_analytics_select:", maxsplit=1)[1]
    row = await AnalyticsPromptRepository(session).get_by_alias(analytics_alias)

    if row is None:
        await callback.message.answer("Аналитический промт не найден.")
        await send_admin_analytics_menu(callback.message, state, session)
        return

    await state.update_data(edit_analytics_alias=row.alias)
    await state.set_state(AdminStates.waiting_edit_analytics_prompt)

    await callback.message.answer(
        f"Вы выбрали:\n{escape(row.comment)} | {escape(row.header)}\n\n"
        "Введите новый текст аналитического промта:"
    )


@router.message(AdminStates.waiting_edit_analytics_prompt)
async def admin_edit_analytics_prompt_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст для изменения аналитического промта.

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

    await state.update_data(edit_analytics_prompt_text=prompt_text)
    await finalize_edit_analytics(message, state, session)


@router.callback_query(F.data == "admin:delete_analytics")
async def admin_delete_analytics_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Запускает сценарий удаления аналитики.

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

    await state.set_state(AdminStates.waiting_delete_analytics_select)
    await send_analytics_selection_menu(
        message=callback.message,
        session=session,
        callback_prefix="admin:delete_analytics_select",
    )


@router.callback_query(F.data.startswith("admin:delete_analytics_select:"))
async def admin_delete_analytics_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор аналитического промта для удаления.

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

    analytics_alias = callback.data.split("admin:delete_analytics_select:", maxsplit=1)[1]
    row = await AnalyticsPromptRepository(session).get_by_alias(analytics_alias)

    if row is None:
        await callback.message.answer("Аналитический промт не найден.")
        await send_admin_analytics_menu(callback.message, state, session)
        return

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(
        ["common_delete_button", "admin_button_analytics_back"]
    )

    keyboard = build_confirm_keyboard(
        edit_text=common_texts["common_delete_button"].value,
        cancel_text=common_texts["admin_button_analytics_back"].value,
        edit_callback="admin:confirm_delete_analytics",
        cancel_callback="admin:analytics_menu",
    )

    await state.update_data(delete_analytics_alias=row.alias)
    await state.set_state(AdminStates.waiting_delete_analytics_confirm)

    await callback.message.answer(
        "Точно удалить этот аналитический промт?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "admin:confirm_delete_analytics")
async def admin_confirm_delete_analytics_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Подтверждает удаление аналитического промта.

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

    data = await state.get_data()
    analytics_alias = data.get("delete_analytics_alias")

    if not analytics_alias:
        await callback.message.answer("Не удалось определить аналитический промт.")
        await send_admin_analytics_menu(callback.message, state, session)
        return

    repo = AnalyticsPromptRepository(session)
    row = await repo.get_by_alias(analytics_alias)

    if row is None:
        await callback.message.answer("Аналитический промт уже удалён.")
        await send_admin_analytics_menu(callback.message, state, session)
        return

    if await is_guest_admin_session(state):
        await callback.message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_analytics_menu(callback.message, state, session)
        return

    game = await GameRepository(session).get_by_game_id(row.game)

    await DeletedPromptRepository(session).create(
        game_name=game.name if game is not None else row.game,
        promt=row.promt,
    )
    await repo.delete_by_alias(row.alias)

    await callback.message.answer("Аналитический промт удалён.")
    await send_admin_analytics_menu(callback.message, state, session)


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