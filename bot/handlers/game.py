# bot/handlers/game.py

"""
Обработчики игрового модуля.

Отвечают за:
- открытие меню конкретной игры;
- запуск конкретного игрового сценария;
- ведение игрового диалога;
- завершение диалога по кнопке;
- работу таймера диалога;
- запуск аналитики после завершения диалога;
- возврат на стартовый экран после аналитики.

Как работает:
- верхний уровень игр строится из таблицы games;
- второй уровень сценариев строится из ui_texts;
- конкретный сценарий берётся через связку ui_texts.game_alias -> game_prompts.alias;
- весь диалог пишется в dialog_messages;
- для ИИ берутся последние 15 пар сообщений;
- ответ ИИ приходит через OpenAI-compatible API;
- после завершения диалога запускается аналитика по таблице analytics_prompts.

Что принимает:
- сообщения и callback-запросы Telegram;
- FSMContext;
- bot;
- сессию БД.

Что возвращает:
- ничего.
"""

from html import escape
import logging
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_keyboards import (
    build_finish_dialog_keyboard,
    build_game_menu_keyboard,
)
from bot.states.game import GameStates
from database.repositories.dialog_message_repository import DialogMessageRepository
from database.repositories.game_prompt_repository import GamePromptRepository
from database.repositories.game_repository import GameRepository
from database.repositories.ui_text_repository import UITextRepository
from services.ai_client import generate_ai_reply
from services.app_logger import AppLogger
from services.dialog_analytics import run_dialog_analysis_and_send_results
from services.game_timer import cancel_dialog_timer, schedule_dialog_timer
from services.images import send_prompt_image_to_chat

router = Router(name="game-router")
logger = logging.getLogger(__name__)

DIALOG_TIMEOUT_SECONDS = 600


async def build_game_root_menu_payload(
    session: AsyncSession,
    game_id: str,
) -> tuple[str, object | None]:
    """
    Готовит текст и клавиатуру меню конкретной игры.

    Что принимает:
    - session: активная сессия БД;
    - game_id: game_id игры.

    Что возвращает:
    - кортеж из текста и клавиатуры.
    """

    game_repo = GameRepository(session)
    ui_repo = UITextRepository(session)

    game = await game_repo.get_by_game_id(game_id)
    if game is None:
        return "Игра не найдена.", None

    greeting_item = await ui_repo.get_by_alias(f"{game_id}_greeting")
    greeting_text = (
        greeting_item.value
        if greeting_item is not None and greeting_item.is_active
        else f"Выберите сценарий игры «{game.name}»."
    )

    second_level_buttons = await ui_repo.get_game_buttons(level=1, game=game_id)
    keyboard = build_game_menu_keyboard(second_level_buttons)

    return greeting_text, keyboard


async def send_game_root_menu(
    message: Message,
    session: AsyncSession,
    game_id: str,
) -> None:
    """
    Отправляет меню конкретной игры через объект Message.

    Что принимает:
    - message: сообщение для ответа;
    - session: активная сессия БД;
    - game_id: game_id игры.

    Что возвращает:
    - ничего.
    """

    text, keyboard = await build_game_root_menu_payload(session=session, game_id=game_id)
    await message.answer(escape(text), reply_markup=keyboard)


async def send_game_root_menu_by_bot(
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    game_id: str,
) -> None:
    """
    Отправляет меню конкретной игры напрямую через bot.send_message.

    Что принимает:
    - bot: объект Telegram-бота;
    - chat_id: id чата;
    - session: активная сессия БД;
    - game_id: game_id игры.

    Что возвращает:
    - ничего.
    """

    text, keyboard = await build_game_root_menu_payload(session=session, game_id=game_id)
    await bot.send_message(chat_id=chat_id, text=escape(text), reply_markup=keyboard)


def build_history_for_ai(history_rows) -> list[dict[str, str]]:
    """
    Преобразует сообщения диалога в формат OpenAI Chat API.

    Отвечает за:
    - преобразование записей dialog_messages в список сообщений role/content;
    - сохранение порядка диалога.

    Как работает:
    - сообщения пользователя переводит в role=user;
    - сообщения ИИ переводит в role=assistant.

    Что принимает:
    - history_rows: список объектов DialogMessage.

    Что возвращает:
    - список словарей формата role/content.
    """

    prepared_history: list[dict[str, str]] = []

    for item in history_rows:
        role = "assistant" if item.comment_owner == "ai" else "user"
        prepared_history.append(
            {
                "role": role,
                "content": item.comment,
            }
        )

    return prepared_history


@router.callback_query(F.data.startswith("main:game_root:"))
async def open_game_root_from_main_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Открывает меню выбранной игры из стартового экрана.

    Что принимает:
    - callback: callback-запрос;
    - session: активная сессия БД.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    game_id = callback.data.split("main:game_root:", maxsplit=1)[1]

    logger.info("Открыто меню игры. game_id=%s", game_id)
    await send_game_root_menu(callback.message, session, game_id)


@router.message(F.text.regexp(r"^/game_\d+$"))
async def game_command_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает команду формата /game_x.

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

    game_id = (message.text or "").replace("/", "", 1).strip()

    logger.info(
        "Открытие меню игры по команде. user_id=%s game_id=%s",
        message.from_user.id if message.from_user else None,
        game_id,
    )

    await send_game_root_menu(message, session, game_id)


@router.callback_query(F.data.startswith("game:start:"))
async def start_game_dialog_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """
    Запускает игровой диалог после выбора сценария второго уровня.

    Что принимает:
    - callback: callback-запрос;
    - state: FSMContext;
    - session: активная сессия БД;
    - bot: объект Telegram-бота.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None or callback.from_user is None:
        return

    _, _, game_id, button_alias = callback.data.split(":", maxsplit=3)

    ui_repo = UITextRepository(session)
    prompt_repo = GamePromptRepository(session)
    dialog_repo = DialogMessageRepository(session)

    selected_button = await ui_repo.get_by_alias(button_alias)
    if selected_button is None or not selected_button.game_alias:
        await callback.message.answer("Сценарий не найден.")
        return

    prompt = await prompt_repo.get_by_alias(selected_button.game_alias)
    if prompt is None:
        await callback.message.answer("Промт не найден.")
        return

    if not prompt.is_active:
        inactive_item = await ui_repo.get_by_alias("game_inactive_message")
        inactive_text = (
            inactive_item.value
            if inactive_item is not None and inactive_item.is_active
            else "Игра пока не активна"
        )

        await AppLogger.warning(
            event="game.prompt_inactive",
            source=__name__,
            message="Попытка запуска неактивного промта",
            payload={
                "user_id": callback.from_user.id,
                "game_id": game_id,
                "prompt_alias": prompt.alias,
            },
            write_to_db=True,
        )

        await callback.message.answer(escape(inactive_text))
        return

    dialog_id = uuid4().hex

    await state.clear()
    await state.set_state(GameStates.in_dialog)
    await state.update_data(
        dialog_id=dialog_id,
        game_id=game_id,
        subgame_id=prompt.alias,
        chat_id=callback.message.chat.id,
    )

    await schedule_dialog_timer(
        bot=bot,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        dialog_id=dialog_id,
        game_id=game_id,
        timeout_seconds=DIALOG_TIMEOUT_SECONDS,
    )

    logger.info(
        "Старт игрового диалога. user_id=%s game_id=%s prompt_alias=%s dialog_id=%s",
        callback.from_user.id,
        game_id,
        prompt.alias,
        dialog_id,
    )

    await AppLogger.info(
        event="dialog.start",
        source=__name__,
        message="Старт игрового диалога",
        payload={
            "user_id": callback.from_user.id,
            "chat_id": callback.message.chat.id,
            "game_id": game_id,
            "prompt_alias": prompt.alias,
            "dialog_id": dialog_id,
        },
        write_to_db=True,
    )

    await callback.message.answer(escape(prompt.conditions))
    await send_prompt_image_to_chat(
        bot=bot,
        chat_id=callback.message.chat.id,
        session=session,
        prompt=prompt,
    )

    greeting_item = await ui_repo.get_by_alias(f"greeting_{prompt.alias}")
    greeting_text = (
        greeting_item.value
        if greeting_item is not None and greeting_item.is_active
        else f"Это приветствие {selected_button.value}"
    )

    await callback.message.answer(escape(greeting_text))

    await dialog_repo.create_message(
        user_id=callback.from_user.id,
        dialog_id=dialog_id,
        comment_owner="ai",
        comment=greeting_text,
        game_id=game_id,
        subgame_id=prompt.alias,
    )


@router.message(GameStates.in_dialog)
async def game_dialog_message_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """
    Обрабатывает очередное пользовательское сообщение внутри игрового диалога.

    Что принимает:
    - message: входящее сообщение;
    - state: FSMContext;
    - session: активная сессия БД;
    - bot: объект Telegram-бота.

    Что возвращает:
    - ничего.
    """

    if message.from_user is None:
        return

    if not message.text:
        await message.answer("Сейчас можно отправлять только текстовые сообщения.")
        return

    data = await state.get_data()
    dialog_id = data.get("dialog_id")
    game_id = data.get("game_id")
    prompt_alias = data.get("subgame_id")

    if not dialog_id or not game_id or not prompt_alias:
        await message.answer("Игровой контекст потерян. Вернитесь в меню игры.")
        await state.clear()
        return

    dialog_repo = DialogMessageRepository(session)
    prompt_repo = GamePromptRepository(session)
    ui_repo = UITextRepository(session)

    await dialog_repo.create_message(
        user_id=message.from_user.id,
        dialog_id=dialog_id,
        comment_owner="user",
        comment=message.text.strip(),
        game_id=game_id,
        subgame_id=prompt_alias,
    )

    prompt = await prompt_repo.get_by_alias(prompt_alias)
    if prompt is None:
        await message.answer("Промт не найден. Диалог завершён.")
        await cancel_dialog_timer(message.from_user.id)
        await state.clear()
        await send_game_root_menu(message, session, game_id)
        return

    if not prompt.is_active:
        inactive_item = await ui_repo.get_by_alias("game_inactive_message")
        inactive_text = (
            inactive_item.value
            if inactive_item is not None and inactive_item.is_active
            else "Игра пока не активна"
        )

        await AppLogger.warning(
            event="dialog.prompt_became_inactive",
            source=__name__,
            message="Промт деактивирован во время диалога",
            payload={
                "user_id": message.from_user.id,
                "dialog_id": dialog_id,
                "game_id": game_id,
                "prompt_alias": prompt_alias,
            },
            write_to_db=True,
        )

        await message.answer(escape(inactive_text))
        await cancel_dialog_timer(message.from_user.id)
        await state.clear()
        await send_game_root_menu(message, session, game_id)
        return

    thinking_item = await ui_repo.get_by_alias("thinking_message")
    thinking_text = (
        thinking_item.value
        if thinking_item is not None and thinking_item.is_active
        else "[Думаю...]"
    )

    thinking_message = await message.answer(escape(thinking_text))

    history_rows = await dialog_repo.get_recent_messages(dialog_id=dialog_id, limit=30)
    prepared_history = build_history_for_ai(history_rows)

    await AppLogger.info(
        event="ai.request_started",
        source=__name__,
        message="Начат запрос к ИИ",
        payload={
            "user_id": message.from_user.id,
            "dialog_id": dialog_id,
            "game_id": game_id,
            "prompt_alias": prompt_alias,
            "history_messages_count": len(prepared_history),
        },
        write_to_db=True,
    )

    try:
        ai_reply = await generate_ai_reply(
            prompt_text=prompt.prompt_text,
            history_messages=prepared_history,
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Ошибка запроса к ИИ: %s", error)

        try:
            await thinking_message.delete()
        except Exception:  # noqa: BLE001
            logger.warning("Не удалось удалить сообщение [Думаю...] после ошибки ИИ")

        await AppLogger.error(
            event="ai.request_failed",
            source=__name__,
            message="Ошибка при получении ответа от ИИ",
            payload={
                "user_id": message.from_user.id,
                "dialog_id": dialog_id,
                "game_id": game_id,
                "prompt_alias": prompt_alias,
                "error": str(error),
            },
            write_to_db=True,
        )

        await message.answer("Не удалось получить ответ ИИ. Попробуйте отправить сообщение ещё раз.")
        return

    try:
        await thinking_message.delete()
    except Exception:  # noqa: BLE001
        logger.warning("Не удалось удалить сообщение [Думаю...]")

    await send_prompt_image_to_chat(
        bot=bot,
        chat_id=message.chat.id,
        session=session,
        prompt=prompt,
    )

    finish_button_item = await ui_repo.get_by_alias("finish_feedback_button")
    finish_button_text = (
        finish_button_item.value
        if finish_button_item is not None and finish_button_item.is_active
        else "Дай обратную связь"
    )

    await dialog_repo.create_message(
        user_id=message.from_user.id,
        dialog_id=dialog_id,
        comment_owner="ai",
        comment=ai_reply,
        game_id=game_id,
        subgame_id=prompt_alias,
    )

    await AppLogger.info(
        event="ai.request_finished",
        source=__name__,
        message="Ответ ИИ успешно получен",
        payload={
            "user_id": message.from_user.id,
            "dialog_id": dialog_id,
            "game_id": game_id,
            "prompt_alias": prompt_alias,
            "reply_length": len(ai_reply),
        },
        write_to_db=True,
    )

    await message.answer(
        escape(ai_reply),
        reply_markup=build_finish_dialog_keyboard(finish_button_text),
    )


@router.callback_query(F.data == "game:finish_feedback")
async def finish_dialog_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """
    Завершает игровой диалог по кнопке пользователя и запускает аналитику.

    Что принимает:
    - callback: callback-запрос;
    - state: FSMContext;
    - session: активная сессия БД;
    - bot: объект Telegram-бота.

    Что возвращает:
    - ничего.
    """

    await callback.answer()

    if callback.message is None or callback.from_user is None:
        return

    data = await state.get_data()
    dialog_id = data.get("dialog_id")
    game_id = data.get("game_id")

    await cancel_dialog_timer(callback.from_user.id)

    if not dialog_id or not game_id:
        from bot.handlers.start import send_start_screen_by_bot

        await send_start_screen_by_bot(
            bot=bot,
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id,
            session=session,
            state=state,
        )
        return

    await state.set_state(GameStates.analyzing_dialog)

    await AppLogger.info(
        event="dialog.finish_by_user",
        source=__name__,
        message="Диалог завершён пользователем, запускаем аналитику",
        payload={
            "user_id": callback.from_user.id,
            "game_id": game_id,
            "dialog_id": dialog_id,
        },
        write_to_db=True,
    )

    await run_dialog_analysis_and_send_results(
        bot=bot,
        chat_id=callback.message.chat.id,
        session=session,
        dialog_id=dialog_id,
        game_id=game_id,
    )

    from bot.handlers.start import send_start_screen_by_bot

    await send_start_screen_by_bot(
        bot=bot,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        session=session,
        state=state,
    )
