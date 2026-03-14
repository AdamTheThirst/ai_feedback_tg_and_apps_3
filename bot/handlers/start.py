# bot/handlers/start.py

"""
Обработчики стартового экрана.

Отвечают за:
- команду /start;
- вывод стартового приветствия;
- вывод стартового меню с inline-кнопками;
- обработку заглушек Энциклопедия и Личный кабинет.

Как работает:
- очищает текущее состояние;
- переводит пользователя в базовое состояние FSM;
- получает тексты из базы;
- отправляет приветствие и клавиатуру.

Что принимает:
- входящие сообщения и callback-запросы Telegram;
- FSMContext;
- сессию базы данных.

Что возвращает:
- ничего.
"""

import json
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_keyboards import build_start_menu_keyboard
from bot.states.common import MainMenuStates
from database.repositories.ui_text_repository import UITextRepository


router = Router(name="start-router")


def build_technical_user_block(message: Message) -> str:
    """
    Собирает технический блок с данными пользователя.

    Отвечает за:
    - формирование отладочной информации для текущего пользователя.

    Как работает:
    - берёт chat_id;
    - берёт user_id;
    - берёт все доступные данные из объекта from_user;
    - превращает их в красивую строку.

    Что принимает:
    - message: входящее сообщение Telegram.

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

    Отвечает за:
    - перевод пользователя в исходное состояние FSM;
    - получение стартового приветствия из БД;
    - получение кнопок стартового меню;
    - добавление технической информации в сообщение.

    Как работает:
    - очищает текущее состояние;
    - устанавливает MainMenuStates.idle;
    - получает текст start_greeting из базы;
    - получает игровые кнопки первого уровня;
    - получает тексты кнопок-заглушек;
    - отправляет итоговое сообщение пользователю.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.clear()
    await state.set_state(MainMenuStates.idle)

    ui_repo = UITextRepository(session)

    start_text = await ui_repo.get_by_alias("start_greeting")
    greeting_text = "Привет, это текст приветствия первого экрана"
    if start_text is not None and start_text.is_active:
        greeting_text = start_text.value

    first_level_game_buttons = await ui_repo.get_game_buttons(level=0)
    static_buttons = await ui_repo.get_many_by_aliases(
        ["btn_encyclopedia", "btn_profile"]
    )

    encyclopedia_text = static_buttons["btn_encyclopedia"].value
    profile_text = static_buttons["btn_profile"].value

    keyboard = build_start_menu_keyboard(
        first_level_game_buttons=first_level_game_buttons,
        encyclopedia_text=encyclopedia_text,
        profile_text=profile_text,
    )

    # ТЕХНИЧЕСКИЙ БЛОК: этот кусок можно потом просто закомментировать целиком.
    technical_info = build_technical_user_block(message)

    final_text = f"{escape(greeting_text)}{technical_info}"
    await message.answer(final_text, reply_markup=keyboard)


@router.message(Command("start"))
async def start_command_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает команду /start.

    Отвечает за:
    - запуск стартового сценария приложения;
    - выход из админки и других состояний;
    - показ первого экрана.

    Как работает:
    - вызывает общую функцию send_start_screen.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await send_start_screen(message, state, session)


@router.callback_query(F.data == "main:stub:encyclopedia")
async def encyclopedia_stub_handler(callback: CallbackQuery) -> None:
    """
    Обрабатывает нажатие на кнопку Энциклопедия.

    Отвечает за:
    - временную заглушку для неактивного раздела.

    Как работает:
    - отвечает на callback;
    - отправляет пользователю временное сообщение.

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
    Обрабатывает нажатие на кнопку Личный кабинет.

    Отвечает за:
    - временную заглушку для неактивного раздела.

    Как работает:
    - отвечает на callback;
    - отправляет пользователю временное сообщение.

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