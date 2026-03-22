# bot/handlers/start.py

"""
Обработчики стартового экрана.

Отвечают за:
- команду /start;
- первичную регистрацию пользователя в боте;
- запрос имени пользователя при первом запуске;
- вывод стартового приветствия;
- вывод стартового меню;
- обработку заглушек Энциклопедия и Личный кабинет;
- выход из активного игрового диалога при необходимости;
- отправку стартового экрана напрямую через bot.send_message.

Как работает:
- при /start очищает текущее состояние;
- отменяет активный таймер игрового диалога;
- проверяет пользователя в таблице users;
- если пользователя нет, создаёт запись и просит ввести имя;
- если имя ещё не заполнено, тоже просит ввести имя;
- после заполнения имени показывает стартовый экран.

Что принимает:
- сообщения Telegram;
- callback-запросы Telegram;
- FSMContext;
- сессию БД.

Что возвращает:
- ничего.
"""

import json
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_keyboards import build_start_menu_keyboard
from bot.states.common import MainMenuStates
from bot.states.user import UserStates
from database.repositories.game_repository import GameRepository
from database.repositories.ui_text_repository import UITextRepository
from database.repositories.user_repository import UserRepository
from services.game_timer import cancel_dialog_timer

router = Router(name="start-router")
logger = logging.getLogger(__name__)

ASK_NAME_TEXT = "Пожалуйста, введите своё имя (это имя будет использоваться только в боте)"


def build_technical_user_block(message: Message) -> str:
    """
    Собирает технический блок с данными пользователя.

    Что принимает:
    - message: входящее сообщение.

    Что возвращает:
    - строку с технической информацией.
    """

    user_data = {}

    if message.from_user is not None:
        user_data = message.from_user.model_dump(exclude_none=True)

    pretty_user_data = json.dumps(
        user_data,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    technical_block = (
        "\n\n"
        "Техническая информация\n"
        f"chat_id: `{message.chat.id}`\n"
        f"user_id: `{message.from_user.id if message.from_user else 'unknown'}`\n"
        "user_data:\n"
        f"{escape(pretty_user_data)}"
    )
    return technical_block


def build_technical_user_block_from_ids(chat_id: int, user_id: int) -> str:
    """
    Собирает технический блок по chat_id и user_id для сценариев,
    где стартовый экран отправляется напрямую через bot.send_message.

    Что принимает:
    - chat_id: id чата;
    - user_id: id пользователя.

    Что возвращает:
    - строку с технической информацией.
    """

    technical_block = (
        "\n\n"
        "Техническая информация\n"
        f"chat_id: `{chat_id}`\n"
        f"user_id: `{user_id}`\n"
        "user_data:\n"
        "недоступно при отправке через bot.send_message"
    )
    return technical_block


async def build_start_screen_payload(
    session: AsyncSession,
) -> tuple[str, object]:
    """
    Готовит текст приветствия и клавиатуру стартового экрана.

    Что принимает:
    - session: активная сессия БД.

    Что возвращает:
    - кортеж из текста приветствия и клавиатуры.
    """

    ui_repo = UITextRepository(session)
    game_repo = GameRepository(session)

    start_text = await ui_repo.get_by_alias("start_greeting")
    greeting_text = "Привет, это текст приветствия первого экрана"

    if start_text is not None and start_text.is_active:
        greeting_text = start_text.value

    games = await game_repo.list_all()
    static_buttons = await ui_repo.get_many_by_aliases(
        ["btn_encyclopedia", "btn_profile"]
    )

    encyclopedia_text = static_buttons["btn_encyclopedia"].value
    profile_text = static_buttons["btn_profile"].value

    keyboard = build_start_menu_keyboard(
        games=games,
        encyclopedia_text=encyclopedia_text,
        profile_text=profile_text,
    )

    return greeting_text, keyboard


async def ensure_user_exists_or_request_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> bool:
    """
    Проверяет, зарегистрирован ли пользователь в таблице users.

    Как работает:
    - если записи нет, создаёт пользователя без имени;
    - если имя пустое, переводит пользователя в состояние ожидания имени;
    - если всё заполнено, разрешает переход к стартовому экрану.

    Что принимает:
    - message: входящее сообщение;
    - state: FSMContext;
    - session: активная сессия БД.

    Что возвращает:
    - True, если можно продолжать сценарий;
    - False, если у пользователя нужно запросить имя.
    """

    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return False

    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(message.from_user.id)

    if user is None:
        await user_repo.create_placeholder(user_id=message.from_user.id)

        logger.info(
            "Создан новый пользователь без имени. user_id=%s",
            message.from_user.id,
        )

        await state.clear()
        await state.set_state(UserStates.waiting_name)
        await message.answer(ASK_NAME_TEXT)
        return False

    if not user.name:
        await state.clear()
        await state.set_state(UserStates.waiting_name)
        await message.answer(ASK_NAME_TEXT)
        return False

    return True


async def send_start_screen(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Отправляет пользователю стартовый экран приложения.

    Что принимает:
    - message: входящее сообщение;
    - state: FSMContext;
    - session: активная сессия БД.

    Что возвращает:
    - ничего.
    """

    if message.from_user is not None:
        await cancel_dialog_timer(message.from_user.id)

    await state.clear()
    await state.set_state(MainMenuStates.idle)

    greeting_text, keyboard = await build_start_screen_payload(session=session)

    # ТЕХНИЧЕСКИЙ БЛОК: этот кусок можно потом просто закомментировать целиком.
    # technical_info = build_technical_user_block(message)
    # final_text = f"{escape(greeting_text)}{technical_info}"

    logger.info(
        "Показан стартовый экран. user_id=%s chat_id=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
    )
    await message.answer(final_text, reply_markup=keyboard)


async def send_start_screen_by_bot(
    bot: Bot,
    chat_id: int,
    user_id: int,
    session: AsyncSession,
    state: FSMContext | None = None,
) -> None:
    """
    Отправляет стартовый экран напрямую через bot.send_message.

    Как работает:
    - при наличии state очищает его и переводит пользователя в idle;
    - собирает стартовый экран через те же данные, что и обычный /start;
    - добавляет упрощённый технический блок по chat_id и user_id.

    Что принимает:
    - bot: объект Telegram-бота;
    - chat_id: id чата;
    - user_id: id пользователя;
    - session: активная сессия БД;
    - state: FSMContext или None.

    Что возвращает:
    - ничего.
    """

    if state is not None:
        await state.clear()
        await state.set_state(MainMenuStates.idle)

    greeting_text, keyboard = await build_start_screen_payload(session=session)

    # ТЕХНИЧЕСКИЙ БЛОК: этот кусок можно потом просто закомментировать целиком.
    technical_info = build_technical_user_block_from_ids(chat_id=chat_id, user_id=user_id)
    final_text = f"{escape(greeting_text)}{technical_info}"

    logger.info(
        "Показан стартовый экран через bot.send_message. user_id=%s chat_id=%s",
        user_id,
        chat_id,
    )

    await bot.send_message(
        chat_id=chat_id,
        text=final_text,
        reply_markup=keyboard,
    )


@router.message(Command("start"))
async def start_command_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает команду /start.

    Что принимает:
    - message: входящее сообщение;
    - state: FSMContext;
    - session: активная сессия БД.

    Что возвращает:
    - ничего.
    """

    if message.from_user is not None:
        await cancel_dialog_timer(message.from_user.id)

    if not await ensure_user_exists_or_request_name(message, state, session):
        return

    await send_start_screen(message, state, session)


@router.message(UserStates.waiting_name)
async def user_name_input_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод имени пользователя при первом запуске.

    Как работает:
    - принимает текст имени;
    - сохраняет его в таблицу users;
    - после сохранения отправляет стартовый экран.

    Что принимает:
    - message: входящее сообщение;
    - state: FSMContext;
    - session: активная сессия БД.

    Что возвращает:
    - ничего.
    """

    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    name = (message.text or "").strip()

    if len(name) < 2:
        await message.answer("Имя слишком короткое. Пожалуйста, введите имя ещё раз.")
        return

    user_repo = UserRepository(session)
    await user_repo.update_name(
        user_id=message.from_user.id,
        name=name[:255],
    )

    logger.info(
        "Пользователь сохранил имя. user_id=%s name=%s",
        message.from_user.id,
        name[:255],
    )

    await send_start_screen(message, state, session)


@router.callback_query(F.data == "main:stub:encyclopedia")
async def encyclopedia_stub_handler(callback: CallbackQuery) -> None:
    """
    Обрабатывает временную кнопку-заглушку Энциклопедия.

    Что принимает:
    - callback: callback-запрос.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("Раздел «Энциклопедия» пока не активен.")


@router.callback_query(F.data == "main:stub:profile")
async def profile_stub_handler(callback: CallbackQuery) -> None:
    """
    Обрабатывает временную кнопку-заглушку Личный кабинет.

    Что принимает:
    - callback: callback-запрос.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("Раздел «Личный кабинет» пока не активен.")
