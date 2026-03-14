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
- редактирование приветствия стартового экрана;
- редактирование приветствия админки;
- редактирование текстов кнопок;
- смену пароля администратора;
- добавление новой игры;
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

from html import escape
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.start import send_start_screen
from bot.keyboards.admin_keyboards import (
    build_admin_main_keyboard,
    build_admin_tools_keyboard,
    build_buttons_list_keyboard,
    build_confirm_keyboard,
    build_games_list_keyboard,
)
from bot.states.admin import AdminStates
from database.repositories.admin_login_incident_repository import (
    AdminLoginIncidentRepository,
)
from database.repositories.deleted_prompt_repository import DeletedPromptRepository
from database.repositories.dialog_message_repository import DialogMessageRepository
from database.repositories.game_prompt_repository import GamePromptRepository
from database.repositories.game_repository import GameRepository
from database.repositories.password_repository import PasswordRepository
from database.repositories.ui_text_repository import UITextRepository
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

    keyboard = build_games_list_keyboard(
        games=games,
        cancel_text=common_texts["common_cancel_button"].value,
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

    game_repo = GameRepository(session)
    game = await game_repo.get_by_game_id(game_id)

    if game is None:
        await callback.message.answer("Игра не найдена.")
        await send_admin_main_menu(callback.message, state, session)
        return

    ui_repo = UITextRepository(session)
    common_texts = await ui_repo.get_many_by_aliases(
        ["common_cancel_button"]
    )

    keyboard = build_confirm_keyboard(
        edit_text="Удалить",
        cancel_text=common_texts["common_cancel_button"].value,
        edit_callback="admin:confirm_delete_game",
    )

    await state.update_data(delete_game_id=game.game_id, delete_game_name=game.name)
    await state.set_state(AdminStates.waiting_delete_game_confirm)

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
    Подтверждает и выполняет удаление игры.

    Отвечает за:
    - перенос связанных промтов в deleted_prompts;
    - удаление связанных промтов;
    - удаление связанных UI-текстов игры;
    - удаление связанных сообщений диалогов;
    - удаление самой игры;
    - блокировку сохранения в гостевом режиме.

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
    guest_mode = await is_guest_admin_session(state)

    await state.update_data(delete_game_id=None, delete_game_name=None)

    if not game_id or not game_name:
        await callback.message.answer("Данные для удаления игры не найдены.")
        await send_admin_main_menu(callback.message, state, session)
        return

    if guest_mode:
        logger.info(
            "Гость попытался удалить игру. user_id=%s game_id=%s",
            callback.from_user.id if callback.from_user else None,
            game_id,
        )
        await callback.message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_main_menu(callback.message, state, session)
        return

    game_repo = GameRepository(session)
    prompt_repo = GamePromptRepository(session)
    ui_repo = UITextRepository(session)
    dialog_repo = DialogMessageRepository(session)
    deleted_prompt_repo = DeletedPromptRepository(session)

    game = await game_repo.get_by_game_id(game_id)
    if game is None:
        await callback.message.answer("Игра уже удалена или не найдена.")
        await send_admin_main_menu(callback.message, state, session)
        return

    prompts = await prompt_repo.list_by_game_id(game_id)

    for prompt in prompts:
        await deleted_prompt_repo.create(
            game_name=game.name,
            promt=prompt.prompt_text,
        )

    await prompt_repo.delete_by_game_id(game_id)
    await ui_repo.delete_by_game_id(game_id)
    await dialog_repo.delete_by_game_id(game_id)
    await game_repo.delete_by_game_id(game_id)

    logger.info(
        "Игра удалена. game_id=%s game_name=%s user_id=%s",
        game.game_id,
        game.name,
        callback.from_user.id if callback.from_user else None,
    )

    await callback.message.answer(f"Игра {escape(game.name)} удалена.")
    await send_admin_main_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:add_prompt")
async def admin_add_prompt_stub_handler(callback: CallbackQuery) -> None:
    """
    Временная заглушка для добавления промта.

    Что принимает:
    - callback: callback-запрос Telegram.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("Добавление промта будет реализовано следующим шагом.")


@router.callback_query(F.data == "admin:edit_prompts")
async def admin_edit_prompts_stub_handler(callback: CallbackQuery) -> None:
    """
    Временная заглушка для изменения промтов.

    Что принимает:
    - callback: callback-запрос Telegram.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("Изменение промтов будет реализовано следующим шагом.")


@router.callback_query(F.data == "admin:toggle_prompt")
async def admin_toggle_prompt_stub_handler(callback: CallbackQuery) -> None:
    """
    Временная заглушка для активации и деактивации промтов.

    Что принимает:
    - callback: callback-запрос Telegram.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("Активация и деактивация промтов будет реализована следующим шагом.")


@router.callback_query(F.data == "admin:delete_prompt")
async def admin_delete_prompt_stub_handler(callback: CallbackQuery) -> None:
    """
    Временная заглушка для удаления промта.

    Что принимает:
    - callback: callback-запрос Telegram.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("Удаление промта будет реализовано следующим шагом.")


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


@router.callback_query(F.data.startswith("admin:button_select:"))
async def admin_button_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор кнопки для редактирования.

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

    selected_alias = callback.data.split("admin:button_select:", maxsplit=1)[1]

    ui_repo = UITextRepository(session)
    selected_button = await ui_repo.get_by_alias(selected_alias)
    current_value = selected_button.value if selected_button is not None else "Не найдено"

    await state.update_data(target_button_alias=selected_alias)
    await state.set_state(AdminStates.waiting_new_button_text)

    await callback.message.answer(
        f"Текущий текст кнопки:\n{escape(current_value)}\n\n"
        "Введите новый текст, от 2 до 30 символов"
    )


@router.message(AdminStates.waiting_new_button_text)
async def admin_new_button_text_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст выбранной кнопки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()
    data = await state.get_data()
    button_alias = data.get("target_button_alias")
    guest_mode = await is_guest_admin_session(state)

    if button_alias is not None and 2 <= len(new_text) <= 30:
        if guest_mode:
            logger.info(
                "Гость попытался изменить текст кнопки. user_id=%s button_alias=%s",
                message.from_user.id if message.from_user else None,
                button_alias,
            )
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            ui_repo = UITextRepository(session)
            await ui_repo.update_value(button_alias, new_text)
            await message.answer("Текст кнопки обновлён.")
    else:
        await message.answer("Некорректная длина текста. Возвращаю в админку.")

    await state.update_data(target_button_alias=None)
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
async def admin_current_password_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод текущего пароля при смене пароля.

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

    guest_mode = await is_guest_admin_session(state)
    if guest_mode:
        await state.set_state(AdminStates.waiting_new_password)
        await message.answer("Введите новый пароль:")
        return

    raw_password = (message.text or "").strip()
    password_repo = PasswordRepository(session)
    admin_password_row = await password_repo.get_by_user_id(ADMIN_USER_ID)

    if admin_password_row is None:
        await message.answer("Пароль администратора не найден.")
        await send_start_screen(message, state, session)
        return

    is_password_valid = verify_password(raw_password, admin_password_row.admin)

    if not is_password_valid:
        await message.answer("Текущий пароль неверный. Возврат на стартовый экран.")
        await send_start_screen(message, state, session)
        return

    if message.from_user.id != ADMIN_USER_ID:
        await register_unauthorized_admin_attempt(message, session)
        await message.answer("Доступ запрещён. Попытка зафиксирована.")
        await send_start_screen(message, state, session)
        return

    await state.set_state(AdminStates.waiting_new_password)
    await message.answer("Введите новый пароль:")


@router.message(AdminStates.waiting_new_password)
async def admin_new_password_handler(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает ввод нового пароля.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    new_password = (message.text or "").strip()
    await state.update_data(new_password=new_password)
    await state.set_state(AdminStates.waiting_new_password_confirm)
    await message.answer("Повторно введите новый пароль:")


@router.message(AdminStates.waiting_new_password_confirm)
async def admin_new_password_confirm_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает подтверждение нового пароля.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    data = await state.get_data()
    first_password = data.get("new_password", "")
    second_password = (message.text or "").strip()
    guest_mode = await is_guest_admin_session(state)

    if not first_password or first_password != second_password:
        await message.answer("Пароли не совпали. Возвращаю в админку.")
        await state.update_data(new_password=None)
        await send_admin_main_menu(message, state, session)
        return

    if guest_mode:
        logger.info(
            "Гость попытался изменить пароль администратора. user_id=%s",
            message.from_user.id if message.from_user else None,
        )
        await state.update_data(new_password=None)
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_main_menu(message, state, session)
        return

    password_repo = PasswordRepository(session)
    await password_repo.update_password_hash(
        user_id=ADMIN_USER_ID,
        new_password_hash=hash_password(second_password),
    )

    logger.info(
        "Пароль администратора изменён. user_id=%s",
        message.from_user.id if message.from_user else None,
    )

    await state.update_data(new_password=None)
    await message.answer("Пароль успешно изменён.")
    await send_admin_main_menu(message, state, session)


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
    await state.update_data(
        delete_game_id=None,
        delete_game_name=None,
        target_button_alias=None,
        new_password=None,
    )
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