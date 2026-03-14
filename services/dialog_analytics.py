# services/dialog_analytics.py

"""
Сервис аналитики завершённого диалога.

Отвечает за:
- сбор всего диалога по dialog_id;
- приведение диалога к единому текстовому блоку;
- последовательный запуск аналитических промтов по игре;
- разбор JSON-ответов ИИ;
- отправку пользователю результатов аналитики;
- подсчёт общей суммы баллов.

Как работает:
- берёт все сообщения диалога из таблицы dialog_messages;
- сортирует их по created_at и id;
- собирает единый блок текста;
- загружает все аналитические промты для game_id;
- по очереди отправляет каждый аналитический промт и весь текст диалога в ИИ;
- ожидает JSON вида {"rating": ..., "text": ...};
- показывает пользователю результаты по очереди;
- в конце отправляет общую сумму баллов.

Что принимает:
- bot: объект Telegram-бота;
- chat_id: id чата;
- session: активная сессия БД;
- dialog_id: id завершённого диалога;
- game_id: game_id игры.

Что возвращает:
- общую сумму баллов типа float.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from html import escape
from typing import Any

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.repositories.analytics_prompt_repository import AnalyticsPromptRepository
from database.repositories.dialog_message_repository import DialogMessageRepository
from database.repositories.ui_text_repository import UITextRepository
from services.ai_client import get_ai_client
from services.app_logger import AppLogger

logger = logging.getLogger(__name__)

ANALYSIS_RESULT_JSON_INSTRUCTION = """
Ниже уже дан аналитический промт.
Ты обязан строго выполнить именно его на основе переданного диалога.

Верни ТОЛЬКО JSON без пояснений и без markdown:
{
  "rating": 0,
  "text": "..."
}

Требования:
- rating — числовая оценка по этому аналитическому промту;
- text — текст результата аналитики на русском языке;
- никаких дополнительных полей;
- никаких комментариев вне JSON.
""".strip()


@dataclass(slots=True)
class DialogAnalysisResult:
    """
    Структура результата одного аналитического шага.

    Отвечает за:
    - хранение оценки;
    - хранение текста аналитики.

    Что принимает:
    - rating: числовая оценка;
    - text: текст аналитики.

    Что возвращает:
    - объект DialogAnalysisResult.
    """

    rating: float
    text: str


def build_dialog_text(dialog_rows: list[Any]) -> str:
    """
    Собирает единый текстовый блок диалога для аналитики.

    Как работает:
    - проходит по всем сообщениям диалога в уже отсортированном порядке;
    - для сообщений пользователя пишет префикс "Пользователь сказал -";
    - для сообщений ИИ пишет префикс "ИИ ответил -".

    Что принимает:
    - dialog_rows: список объектов DialogMessage.

    Что возвращает:
    - единый текст диалога.
    """

    lines: list[str] = []

    for item in dialog_rows:
        if item.comment_owner == "user":
            prefix = "Пользователь сказал -"
        else:
            prefix = "ИИ ответил -"

        lines.append(f"{prefix} {item.comment}")

    return "\n".join(lines).strip()


def _normalize_message_content(raw_content: Any) -> str:
    """
    Нормализует содержимое ответа модели в обычную строку.

    Что принимает:
    - raw_content: содержимое ответа модели.

    Что возвращает:
    - строку ответа.
    """

    if raw_content is None:
        return ""

    if isinstance(raw_content, str):
        return raw_content.strip()

    if isinstance(raw_content, list):
        parts: list[str] = []

        for item in raw_content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_value = item.get("text", "")
                if isinstance(text_value, str) and text_value.strip():
                    parts.append(text_value.strip())

        return "\n".join(parts).strip()

    return str(raw_content).strip()


def _extract_json_object(raw_text: str) -> dict:
    """
    Извлекает JSON-объект из текста ответа модели.

    Что принимает:
    - raw_text: сырой текст ответа.

    Что возвращает:
    - словарь с JSON-данными.

    Что выбрасывает:
    - ValueError, если JSON извлечь не удалось.
    """

    cleaned = raw_text.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match is None:
        raise ValueError("JSON-объект не найден в ответе ИИ")

    return json.loads(match.group(0))


def _normalize_rating(raw_rating: Any) -> float:
    """
    Приводит rating из ответа ИИ к числу.

    Что принимает:
    - raw_rating: значение rating из JSON.

    Что возвращает:
    - число float.
    """

    if isinstance(raw_rating, (int, float)):
        return float(raw_rating)

    if isinstance(raw_rating, str):
        cleaned = raw_rating.replace(",", ".").strip()
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if match is not None:
            return float(match.group(0))

    return 0.0


def format_score(score: float) -> str:
    """
    Красиво форматирует оценку или сумму баллов.

    Что принимает:
    - score: числовое значение.

    Что возвращает:
    - строку без лишних нулей.
    """

    if float(score).is_integer():
        return str(int(score))

    return f"{score:.2f}".rstrip("0").rstrip(".")


def _request_dialog_analysis(prompt_text: str, dialog_text: str) -> DialogAnalysisResult:
    """
    Выполняет синхронный запрос к ИИ для одного аналитического промта.

    Что принимает:
    - prompt_text: текст аналитического промта;
    - dialog_text: полный текст диалога.

    Что возвращает:
    - объект DialogAnalysisResult.
    """

    client = get_ai_client()

    system_text = (
        f"{prompt_text}\n\n"
        f"{ANALYSIS_RESULT_JSON_INSTRUCTION}"
    )

    response = client.chat.completions.create(
        model=settings.ai_model,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": dialog_text},
        ],
        max_tokens=500,
        temperature=0.2,
        top_p=0.8,
    )

    if not response.choices:
        return DialogAnalysisResult(
            rating=0.0,
            text="Не удалось получить результат аналитики.",
        )

    raw_content = getattr(response.choices[0].message, "content", None)
    content_text = _normalize_message_content(raw_content)

    try:
        data = _extract_json_object(content_text)
    except Exception as error:  # noqa: BLE001
        logger.exception("Не удалось разобрать JSON результата аналитики: %s", error)
        return DialogAnalysisResult(
            rating=0.0,
            text="Не удалось корректно разобрать результат аналитики.",
        )

    rating = _normalize_rating(data.get("rating"))
    text = str(data.get("text", "")).strip()

    if not text:
        text = "Аналитика не вернула текст результата."

    return DialogAnalysisResult(
        rating=rating,
        text=text,
    )


async def generate_dialog_analysis(prompt_text: str, dialog_text: str) -> DialogAnalysisResult:
    """
    Асинхронно запускает один аналитический шаг.

    Что принимает:
    - prompt_text: текст аналитического промта;
    - dialog_text: полный текст диалога.

    Что возвращает:
    - объект DialogAnalysisResult.
    """

    return await asyncio.to_thread(_request_dialog_analysis, prompt_text, dialog_text)


async def run_dialog_analysis_and_send_results(
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    dialog_id: str,
    game_id: str,
) -> float:
    """
    Выполняет полный цикл аналитики завершённого диалога и отправляет результаты пользователю.

    Как работает:
    - показывает сообщение о начале анализа;
    - получает все сообщения диалога;
    - собирает единый текстовый блок;
    - печатает его в консоль для отладки;
    - загружает аналитические промты для игры;
    - поочерёдно запускает каждый аналитический промт;
    - удаляет сообщение ожидания;
    - отправляет результаты по одному с паузой 0.2 секунды;
    - отправляет общую сумму баллов.

    Что принимает:
    - bot: объект Telegram-бота;
    - chat_id: id чата;
    - session: активная сессия БД;
    - dialog_id: id завершённого диалога;
    - game_id: game_id игры.

    Что возвращает:
    - общую сумму баллов.
    """

    ui_repo = UITextRepository(session)
    dialog_repo = DialogMessageRepository(session)
    analytics_repo = AnalyticsPromptRepository(session)

    ui_items = await ui_repo.get_many_by_aliases(
        [
            "analysis_in_progress_message",
            "analysis_no_prompts_message",
            "analysis_empty_dialog_message",
            "analysis_total_score_message",
        ]
    )

    in_progress_text = ui_items["analysis_in_progress_message"].value
    no_prompts_text = ui_items["analysis_no_prompts_message"].value
    empty_dialog_text = ui_items["analysis_empty_dialog_message"].value
    total_score_template = ui_items["analysis_total_score_message"].value

    wait_message = await bot.send_message(
        chat_id=chat_id,
        text=escape(in_progress_text),
    )

    await AppLogger.info(
        event="dialog.analysis_started",
        source=__name__,
        message="Запущен анализ завершённого диалога",
        payload={
            "chat_id": chat_id,
            "dialog_id": dialog_id,
            "game_id": game_id,
        },
        write_to_db=True,
    )

    dialog_rows = await dialog_repo.get_all_messages(dialog_id=dialog_id)

    if not dialog_rows:
        with suppress(Exception):
            await wait_message.delete()

        await bot.send_message(chat_id=chat_id, text=escape(empty_dialog_text))
        return 0.0

    dialog_text = build_dialog_text(dialog_rows)

    # ОТЛАДОЧНАЯ ИНФОРМАЦИЯ - В РЕЛИЗЕ ЗАКОММЕНТИТЬ
    print("\n=== ПОЛНЫЙ ТЕКСТ ДИАЛОГА ДЛЯ АНАЛИТИКИ ===")
    print(dialog_text)
    print("=== КОНЕЦ ПОЛНОГО ТЕКСТА ДИАЛОГА ===\n")

    analytics_prompts = await analytics_repo.list_by_game(game_id=game_id)

    if not analytics_prompts:
        with suppress(Exception):
            await wait_message.delete()

        await bot.send_message(chat_id=chat_id, text=escape(no_prompts_text))
        return 0.0

    results_to_send: list[str] = []
    total_score = 0.0

    for analytics_prompt in analytics_prompts:
        try:
            result = await generate_dialog_analysis(
                prompt_text=analytics_prompt.promt,
                dialog_text=dialog_text,
            )
        except Exception as error:  # noqa: BLE001
            logger.exception("Ошибка выполнения аналитического промта: %s", error)

            await AppLogger.error(
                event="dialog.analysis_step_failed",
                source=__name__,
                message="Ошибка выполнения аналитического промта",
                payload={
                    "chat_id": chat_id,
                    "dialog_id": dialog_id,
                    "game_id": game_id,
                    "analytics_alias": analytics_prompt.alias,
                    "error": str(error),
                },
                write_to_db=True,
            )

            result = DialogAnalysisResult(
                rating=0.0,
                text="Не удалось выполнить один из аналитических шагов.",
            )

        total_score += result.rating
        results_to_send.append(
            f"{format_score(result.rating)}\n\r{result.text}"
        )

    with suppress(Exception):
        await wait_message.delete()

    for item in results_to_send:
        await bot.send_message(chat_id=chat_id, text=escape(item))
        await asyncio.sleep(0.2)

    if "{score}" in total_score_template:
        total_score_text = total_score_template.format(score=format_score(total_score))
    else:
        total_score_text = f"{total_score_template} {format_score(total_score)}"

    await bot.send_message(chat_id=chat_id, text=escape(total_score_text))

    await AppLogger.info(
        event="dialog.analysis_finished",
        source=__name__,
        message="Анализ завершён успешно",
        payload={
            "chat_id": chat_id,
            "dialog_id": dialog_id,
            "game_id": game_id,
            "analytics_count": len(analytics_prompts),
            "total_score": format_score(total_score),
        },
        write_to_db=True,
    )

    return total_score
