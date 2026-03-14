# app/bot/handlers/game.py

"""
Файл: app/bot/handlers/game.py

Обработчик команд вида /game_x.

Отвечает за:
- выход из админки при старте игрового сценария;
- первичную заглушку под будущий игровой блок.

Как работает:
- реагирует на команды /game_1, /game_2 и т.д.;
- очищает текущее состояние;
- отправляет техническое сообщение-заглушку.

Что принимает:
- входящее сообщение Telegram;
- FSMContext.

Что возвращает:
- ничего.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message


router = Router(name="game-router")


@router.message(F.text.regexp(r"^/game_\d+$"))
async def game_command_handler(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает команды формата /game_x.

    Отвечает за:
    - выход из любого текущего состояния, включая админку;
    - первичный вход в игровой поток.

    Как работает:
    - очищает текущее FSM-состояние;
    - отправляет временное сообщение.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await state.clear()

    # ЭТО ЗАГЛУШКА
    await message.answer(
        "Вы вышли из админки и перешли в игровой сценарий. "
        "Сценарий /game_x будет реализован на следующем шаге."
    )