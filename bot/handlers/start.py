# app/bot/handlers/start.py

"""
Файл: app/bot/handlers/start.py

Обработчик команды /start.

Отвечает за:
- перевод пользователя в исходное состояние FSM;
- выход из админки при необходимости;
- отправку стартового приветствия;
- вывод технической информации о пользователе.

Как работает:
- очищает текущее состояние;
- устанавливает базовое состояние MainMenuStates.idle;
- получает текст приветствия из базы;
- отправляет сообщение пользователю.

Что принимает:
- входящее сообщение Telegram;
- FSMContext;
- сессию базы данных.

Что возвращает:
- ничего.
"""

import json
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

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
    - добавление технической информации в сообщение.

    Как работает:
    - очищает текущее состояние;
    - устанавливает MainMenuStates.idle;
    - получает текст start_greeting из базы;
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

    # ТЕХНИЧЕСКИЙ БЛОК: этот кусок можно потом просто закомментировать целиком.
    technical_info = build_technical_user_block(message)

    final_text = f"{escape(greeting_text)}{technical_info}"
    await message.answer(final_text)


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
    - выход из админки, если пользователь был внутри неё;
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