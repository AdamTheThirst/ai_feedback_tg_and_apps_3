# bot/handlers/start.py

"""
Обработчики стартового экрана.

Отвечают за:
- команду /start;
- вывод стартового приветствия;
- вывод стартового меню;
- обработку заглушек Энциклопедия и Личный кабинет;
- выход из активного игрового диалога при необходимости.

Как работает:
- очищает текущее состояние;
- отменяет активный таймер игрового диалога;
- переводит пользователя в базовое состояние;
- получает тексты и список игр из БД;
- отправляет стартовое сообщение с клавиатурой.

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

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_keyboards import build_start_menu_keyboard
from bot.states.common import MainMenuStates
from database.repositories.game_repository import GameRepository
from database.repositories.ui_text_repository import UITextRepository
from services.game_timer import cancel_dialog_timer


router = Router(name="start-router")
logger = logging.getLogger(__name__)


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
        "<b>Техническая информация</b>\n"
        f"chat_id: <code>{message.chat.id}</code>\n"
        f"user_id: <code>{message.from_user.id if message.from_user else 'unknown'}</code>\n"
        "<pre>"
        f"{escape(pretty_user_data)}"
        "</pre>"
    )
    return technical_block


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

    # ТЕХНИЧЕСКИЙ БЛОК: этот кусок можно потом просто закомментировать целиком.
    technical_info = build_technical_user_block(message)

    final_text = f"{escape(greeting_text)}{technical_info}"

    logger.info(
        "Показан стартовый экран. user_id=%s chat_id=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
    )
    await message.answer(final_text, reply_markup=keyboard)


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

    await send_start_screen(message, state, session)


@router.callback_query(F.data == "main:stub:encyclopedia")
async def encyclopedia_stub_handler(callback: CallbackQuery) -> None:
    """
    Обрабатывает кнопку Энциклопедия.

    Что принимает:
    - callback: callback-запрос Telegram.

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
    Обрабатывает кнопку Личный кабинет.

    Что принимает:
    - callback: callback-запрос Telegram.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    # ЭТО ЗАГЛУШКА
    await callback.message.answer("Раздел «Личный кабинет» пока не активен.")