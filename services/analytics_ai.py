# services/analytics_ai.py

"""
Сервис подготовки метаданных аналитического промта через ИИ.

Отвечает за:
- генерацию header, comment и alias для нового аналитического промта;
- нормализацию и безопасный разбор ответа ИИ.

Как работает:
- использует уже настроенный OpenAI-compatible клиент;
- отправляет в ИИ специальный системный промт;
- ожидает JSON-ответ;
- при ошибках использует безопасный fallback.

Что принимает:
- текст аналитического промта.

Что возвращает:
- структурированные данные для записи в БД.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from config import settings
from services.ai_client import get_ai_client

logger = logging.getLogger(__name__)

ANALYTICS_METADATA_SYSTEM_PROMPT = """
Ты анализируешь текст аналитического промта и возвращаешь ТОЛЬКО JSON без пояснений.

Твоя задача:
1) comment — короткий комментарий на русском, строго до 100 символов.
   Он должен максимально чётко объяснять, что делает этот аналитический промт.
2) alias — короткий английский alias в snake_case, только латиница, цифры и underscore.
3) header — очень короткий заголовок на русском, 1 или 2 слова.

Верни ТОЛЬКО JSON формата:
{
  "header": "....",
  "comment": "....",
  "alias": "...."
}
""".strip()


@dataclass(slots=True)
class AnalyticsMetadata:
    """
    Структура метаданных аналитического промта.

    Отвечает за:
    - хранение короткого заголовка;
    - хранение комментария;
    - хранение алиаса.

    Что принимает:
    - header: короткий заголовок;
    - comment: краткий комментарий;
    - alias: alias промта.

    Что возвращает:
    - объект AnalyticsMetadata.
    """

    header: str
    comment: str
    alias: str


def _normalize_message_content(raw_content) -> str:
    """
    Нормализует ответ модели в строку.

    Что принимает:
    - raw_content: содержимое ответа модели.

    Что возвращает:
    - строку с текстом ответа.
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
    - словарь с данными JSON.

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


def _sanitize_alias(raw_alias: str, prompt_text: str) -> str:
    """
    Приводит alias к безопасному формату.

    Что принимает:
    - raw_alias: alias от ИИ;
    - prompt_text: текст аналитического промта.

    Что возвращает:
    - alias в snake_case.
    """

    source = (raw_alias or "").strip()

    if not source:
        source = prompt_text[:50].lower()

    source = source.lower()
    source = re.sub(r"[^a-z0-9_]+", "_", source)
    source = re.sub(r"_+", "_", source).strip("_")

    if not source:
        return "analytics_prompt"

    return source[:80]


def _fallback_header_from_prompt(prompt_text: str) -> str:
    """
    Генерирует fallback-заголовок по тексту промта.

    Что принимает:
    - prompt_text: текст аналитического промта.

    Что возвращает:
    - короткий заголовок.
    """

    words = [item for item in re.split(r"\s+", prompt_text.strip()) if item]

    if not words:
        return "Анализ"

    if len(words) == 1:
        return words[0][:25]

    return f"{words[0][:20]} {words[1][:20]}".strip()


def _fallback_comment() -> str:
    """
    Возвращает безопасный fallback-комментарий.

    Что принимает:
    - ничего.

    Что возвращает:
    - строку комментария.
    """

    return "Анализирует диалог по заданному критерию."


def _request_analytics_metadata(prompt_text: str) -> AnalyticsMetadata:
    """
    Выполняет синхронный запрос к ИИ для генерации метаданных аналитического промта.

    Что принимает:
    - prompt_text: текст аналитического промта.

    Что возвращает:
    - объект AnalyticsMetadata.
    """

    client = get_ai_client()

    response = client.chat.completions.create(
        model=settings.ai_model,
        messages=[
            {"role": "system", "content": ANALYTICS_METADATA_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        max_tokens=200,
        temperature=0.1,
        top_p=0.8,
    )

    if not response.choices:
        return AnalyticsMetadata(
            header=_fallback_header_from_prompt(prompt_text),
            comment=_fallback_comment(),
            alias=_sanitize_alias("", prompt_text),
        )

    raw_content = getattr(response.choices[0].message, "content", None)
    content_text = _normalize_message_content(raw_content)

    try:
        data = _extract_json_object(content_text)
    except Exception as error:  # noqa: BLE001
        logger.exception("Не удалось разобрать JSON метаданных аналитики: %s", error)
        return AnalyticsMetadata(
            header=_fallback_header_from_prompt(prompt_text),
            comment=_fallback_comment(),
            alias=_sanitize_alias("", prompt_text),
        )

    header = str(data.get("header", "")).strip() or _fallback_header_from_prompt(prompt_text)
    comment = str(data.get("comment", "")).strip() or _fallback_comment()
    alias = _sanitize_alias(str(data.get("alias", "")).strip(), prompt_text)

    return AnalyticsMetadata(
        header=header[:120],
        comment=comment[:100],
        alias=alias,
    )


async def generate_analytics_metadata(prompt_text: str) -> AnalyticsMetadata:
    """
    Асинхронно получает метаданные аналитического промта.

    Что принимает:
    - prompt_text: текст аналитического промта.

    Что возвращает:
    - объект AnalyticsMetadata.
    """

    return await asyncio.to_thread(_request_analytics_metadata, prompt_text)
