# services/ai_client.py

"""
Сервис генерации ответа ИИ.

Отвечает за:
- создание клиента OpenAI-compatible API;
- отправку истории диалога в ИИ;
- получение ответа модели;
- нормализацию текста ответа.

Как работает:
- использует официальный Python-клиент OpenAI с base_url;
- выполняет запрос в отдельном потоке через asyncio.to_thread,
  потому что клиент синхронный;
- отправляет system prompt и историю сообщений;
- возвращает готовый текст ответа.

Что принимает:
- prompt_text;
- history_messages.

Что возвращает:
- строку ответа ИИ.
"""

import asyncio
import logging
from typing import Any

from openai import OpenAI

from config import settings


logger = logging.getLogger(__name__)

_ai_client: OpenAI | None = None


def get_ai_client() -> OpenAI:
    """
    Возвращает singleton-клиент для OpenAI-compatible API.

    Отвечает за:
    - ленивую инициализацию клиента;
    - проверку обязательных настроек для ИИ.

    Как работает:
    - при первом вызове создаёт экземпляр OpenAI;
    - при последующих вызовах возвращает уже созданный объект.

    Что принимает:
    - ничего.

    Что возвращает:
    - объект OpenAI.
    """

    global _ai_client

    if _ai_client is not None:
        return _ai_client

    if not settings.ai_base_url:
        raise ValueError("Не найден AI_BASE_URL в .env")

    if not settings.ai_api_token:
        raise ValueError("Не найден AI_API_TOKEN в .env")

    _ai_client = OpenAI(
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_token,
    )
    return _ai_client


def _normalize_message_content(raw_content: Any) -> str:
    """
    Нормализует содержимое ответа модели в обычную строку.

    Отвечает за:
    - приведение разных форматов content к тексту.

    Как работает:
    - если content уже строка, возвращает её;
    - если content список, пытается склеить текстовые части;
    - если content пустой, возвращает пустую строку.

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
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_value = item.get("text", "")
                    if isinstance(text_value, str) and text_value.strip():
                        parts.append(text_value.strip())

        return "\n".join(parts).strip()

    return str(raw_content).strip()


def _request_chat_completion(
    prompt_text: str,
    history_messages: list[dict[str, str]],
) -> str:
    """
    Выполняет синхронный запрос к OpenAI-compatible Chat Completions API.

    Отвечает за:
    - формирование payload для модели;
    - вызов chat.completions.create;
    - извлечение текста ответа.

    Как работает:
    - создаёт список messages с system prompt и историей;
    - отправляет запрос с базовыми параметрами генерации;
    - возвращает текст первой choice.

    Что принимает:
    - prompt_text: системный промт;
    - history_messages: история сообщений формата role/content.

    Что возвращает:
    - строку ответа модели.
    """

    client = get_ai_client()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": prompt_text},
        *history_messages,
    ]

    logger.info(
        "Отправка запроса в ИИ. model=%s messages_count=%s",
        settings.ai_model,
        len(messages),
    )

    chat_response = client.chat.completions.create(
        model=settings.ai_model,
        messages=messages,
        max_tokens=200,
        temperature=0.7,
        top_p=0.8,
    )

    if not chat_response.choices:
        return ""

    first_choice = chat_response.choices[0]
    message = getattr(first_choice, "message", None)

    if message is None:
        return ""

    return _normalize_message_content(getattr(message, "content", None))


async def generate_ai_reply(
    prompt_text: str,
    history_messages: list[dict[str, str]],
) -> str:
    """
    Генерирует ответ ИИ на основе системного промта и истории диалога.

    Отвечает за:
    - безопасный вызов синхронного OpenAI-клиента из асинхронного кода;
    - возврат готового текста ответа.

    Как работает:
    - передаёт синхронный запрос в asyncio.to_thread;
    - получает строку ответа;
    - если ответ пустой, возвращает безопасный fallback.

    Что принимает:
    - prompt_text: системный промт;
    - history_messages: история сообщений в формате OpenAI Chat API.

    Что возвращает:
    - строку ответа ИИ.
    """

    reply_text = await asyncio.to_thread(
        _request_chat_completion,
        prompt_text,
        history_messages,
    )

    if reply_text.strip():
        return reply_text.strip()

    return "Здравствуйте! Я вас услышал."