# bot/handlers/game.py

"""
Обработчики игрового меню.

Отвечают за:
- переход из стартового экрана в игровое меню;
- показ приветствия конкретной игры;
- показ сценариев второго уровня;
- обработку кнопок выбора сценария;
- обработку команд вида /game_x.

Как работает:
- получает game alias из callback_data или команды;
- читает приветствие игры и список кнопок из базы;
- отправляет пользователю игровое меню.

Что принимает:
- сообщения Telegram;
- callback-запросы Telegram;
- FSMContext;
- сессию базы данных.

Что возвращает:
- ничего.
"""

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_keyboards import build_game_menu_keyboard
from database.repositories.ui_text_repository import UITextRepository


router = Router(name="game-router")


async def send_game_root_menu(
    message: Message,
    session: AsyncSession,
    game_alias: str,
) -> None:
    """
    Отправляет пользователю игровое меню выбранной игры.

    Отвечает за:
    - вывод приветствия игры;
    - вывод сценариев второго уровня.

    Как работает:
    - получает текст приветствия по alias формата {game_alias}_greeting;
    - получает кнопки второго уровня по game_alias и level=1;
    - формирует и отправляет сообщение с клавиатурой.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - session: активная сессия базы данных;
    - game_alias: alias игры, например game_0.

    Что возвращает:
    - ничего.
    """

    ui_repo = UITextRepository(session)

    greeting_alias = f"{game_alias}_greeting"
    greeting_item = await ui_repo.get_by_alias(greeting_alias)
    second_level_buttons = await ui_repo.get_game_buttons(level=1, game=game_alias)

    greeting_text = "Игровое меню пока не настроено."
    if greeting_item is not None and greeting_item.is_active:
        greeting_text = greeting_item.value

    keyboard = build_game_menu_keyboard(second_level_buttons=second_level_buttons)
    await message.answer(escape(greeting_text), reply_markup=keyboard)


@router.callback_query(F.data.startswith("main:game_root:"))
async def open_game_root_from_main_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Открывает игровое меню из стартового экрана.

    Отвечает за:
    - переход по кнопке верхнего уровня, например Я-высказывание.

    Как работает:
    - извлекает game_alias из callback_data;
    - вызывает общую функцию отправки игрового меню.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    game_alias = callback.data.split("main:game_root:", maxsplit=1)[1]
    await send_game_root_menu(callback.message, session, game_alias)


@router.message(F.text.regexp(r"^/game_\d+$"))
async def game_command_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает команды формата /game_x.

    Отвечает за:
    - выход из текущего состояния, включая админку;
    - открытие игрового меню, если игра существует.

    Как работает:
    - очищает текущее FSM-состояние;
    - извлекает alias игры из текста команды;
    - показывает соответствующее игровое меню.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.clear()

    game_alias = (message.text or "").replace("/", "", 1).strip()
    await send_game_root_menu(message, session, game_alias)


@router.callback_query(F.data.startswith("game:start:"))
async def game_start_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор конкретного игрового сценария второго уровня.

    Отвечает за:
    - переход из меню игры в конкретный сценарий.

    Как работает:
    - извлекает game_alias и alias кнопки сценария;
    - получает текст выбранной кнопки из базы;
    - отправляет временное сообщение-заглушку.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None:
        return

    _, _, game_alias, button_alias = callback.data.split(":", maxsplit=3)

    ui_repo = UITextRepository(session)
    button_item = await ui_repo.get_by_alias(button_alias)
    button_text = button_item.value if button_item is not None else button_alias

    # ЭТО ЗАГЛУШКА
    await callback.message.answer(
        f"Вы выбрали сценарий: <b>{escape(button_text)}</b>\n"
        f"Игра: <code>{escape(game_alias)}</code>\n\n"
        "Сценарий игры будет реализован на следующем шаге."
    )