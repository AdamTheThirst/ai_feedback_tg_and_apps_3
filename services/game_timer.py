# services/game_timer.py

"""
Сервис таймеров игровых диалогов.

Отвечает за:
- запуск таймера завершения диалога;
- отмену таймера;
- автоматическое завершение диалога по времени.

Как работает:
- хранит in-memory задачи asyncio по user_id;
- через Dispatcher получает доступ к FSM-контексту пользователя;
- по истечении времени завершает диалог и возвращает пользователя в меню игры.

Важно:
- таймер живёт в памяти процесса;
- если бот будет перезапущен, активные таймеры тоже сбросятся.

Что принимает:
- bot;
- dispatcher;
- user_id;
- chat_id;
- dialog_id;
- game_id.

Что возвращает:
- ничего.
"""

import asyncio
from contextlib import suppress
import logging

from aiogram import Bot, Dispatcher

from database.repositories.ui_text_repository import UITextRepository
from database.session import SessionFactory
from services.app_logger import AppLogger


logger = logging.getLogger(__name__)

_dispatcher: Dispatcher | None = None
_timer_tasks: dict[int, asyncio.Task] = {}


def configure_game_timer_service(dispatcher: Dispatcher) -> None:
    """
    Сохраняет Dispatcher для последующей работы с FSM-контекстом пользователя.

    Что принимает:
    - dispatcher: экземпляр Dispatcher.

    Что возвращает:
    - ничего.
    """

    global _dispatcher
    _dispatcher = dispatcher


async def cancel_dialog_timer(user_id: int) -> None:
    """
    Отменяет активный таймер диалога пользователя, если он есть.

    Что принимает:
    - user_id: Telegram user id.

    Что возвращает:
    - ничего.
    """

    task = _timer_tasks.pop(user_id, None)
    if task is None:
        return

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def schedule_dialog_timer(
    bot: Bot,
    user_id: int,
    chat_id: int,
    dialog_id: str,
    game_id: str,
    timeout_seconds: int = 600,
) -> None:
    """
    Запускает новый таймер диалога.

    Как работает:
    - сначала отменяет старый таймер пользователя;
    - затем создаёт новую asyncio-задачу.

    Что принимает:
    - bot: объект Telegram-бота;
    - user_id: Telegram user id;
    - chat_id: id чата;
    - dialog_id: id активного диалога;
    - game_id: game_id игры;
    - timeout_seconds: время тайм-аута в секундах.

    Что возвращает:
    - ничего.
    """

    await cancel_dialog_timer(user_id)

    task = asyncio.create_task(
        _dialog_timeout_worker(
            bot=bot,
            user_id=user_id,
            chat_id=chat_id,
            dialog_id=dialog_id,
            game_id=game_id,
            timeout_seconds=timeout_seconds,
        )
    )
    _timer_tasks[user_id] = task


async def _dialog_timeout_worker(
    bot: Bot,
    user_id: int,
    chat_id: int,
    dialog_id: str,
    game_id: str,
    timeout_seconds: int,
) -> None:
    """
    Фоновая задача тайм-аута диалога.

    Как работает:
    - ждёт timeout_seconds;
    - проверяет, что у пользователя всё ещё активен именно этот dialog_id;
    - очищает состояние;
    - отправляет сообщение о завершении;
    - возвращает пользователя в меню игры.

    Что принимает:
    - bot: объект Telegram-бота;
    - user_id: Telegram user id;
    - chat_id: id чата;
    - dialog_id: id диалога;
    - game_id: game_id игры;
    - timeout_seconds: тайм-аут в секундах.

    Что возвращает:
    - ничего.
    """

    try:
        await asyncio.sleep(timeout_seconds)
    except asyncio.CancelledError:
        logger.info("Таймер диалога отменён. user_id=%s dialog_id=%s", user_id, dialog_id)
        raise

    try:
        if _dispatcher is None:
            logger.error("Сервис таймеров не сконфигурирован: dispatcher отсутствует.")
            return

        state = await _dispatcher.fsm.get_context(
            bot=bot,
            chat_id=chat_id,
            user_id=user_id,
        )
        data = await state.get_data()

        current_dialog_id = data.get("dialog_id")
        current_game_id = data.get("game_id")

        if current_dialog_id != dialog_id or current_game_id != game_id:
            return

        await state.clear()
        _timer_tasks.pop(user_id, None)

        async with SessionFactory() as session:
            ui_repo = UITextRepository(session)
            timeout_item = await ui_repo.get_by_alias("dialog_timeout_message")
            timeout_text = (
                timeout_item.value
                if timeout_item is not None and timeout_item.is_active
                else "Время диалога истекло. Возвращаю к выбору сценария."
            )

            await AppLogger.info(
                event="dialog.timeout",
                source=__name__,
                message="Диалог завершён по таймеру",
                payload={
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "dialog_id": dialog_id,
                    "game_id": game_id,
                },
                write_to_db=True,
            )

            await bot.send_message(chat_id=chat_id, text=timeout_text)

            from bot.handlers.game import send_game_root_menu_by_bot

            await send_game_root_menu_by_bot(
                bot=bot,
                chat_id=chat_id,
                session=session,
                game_id=game_id,
            )
    except Exception as error:  # noqa: BLE001
        logger.exception("Ошибка в таймере диалога: %s", error)
        await AppLogger.error(
            event="dialog.timeout_error",
            source=__name__,
            message="Ошибка фонового таймера диалога",
            payload={
                "user_id": user_id,
                "chat_id": chat_id,
                "dialog_id": dialog_id,
                "game_id": game_id,
                "error": str(error),
            },
            write_to_db=True,
        )