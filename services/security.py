# app/services/security.py

"""
Файл: app/services/security.py

Сервис для работы с паролями.

Отвечает за:
- хэширование паролей;
- проверку пароля по хэшу.

Как работает:
- использует sha256;
- добавляет pepper из настроек приложения;
- сравнивает хэши через hmac.compare_digest.

Что принимает:
- пароль в открытом виде;
- сохранённый хэш.

Что возвращает:
- строку хэша или результат проверки True/False.
"""

import hashlib
import hmac

from config import settings


def hash_password(raw_password: str) -> str:
    """
    Хэширует пароль с использованием pepper.

    Отвечает за:
    - преобразование открытого пароля в безопасную хэш-строку для хранения в БД.

    Как работает:
    - соединяет пароль с секретным pepper;
    - считает sha256-хэш;
    - возвращает hex-представление результата.

    Что принимает:
    - raw_password: пароль в открытом виде.

    Что возвращает:
    - строку с хэшем пароля.
    """

    payload = f"{settings.password_pepper}:{raw_password}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_password(raw_password: str, stored_hash: str) -> bool:
    """
    Проверяет, соответствует ли открытый пароль сохранённому хэшу.

    Отвечает за:
    - безопасную проверку введённого пользователем пароля.

    Как работает:
    - повторно хэширует введённый пароль;
    - сравнивает вычисленный хэш с сохранённым через compare_digest.

    Что принимает:
    - raw_password: пароль, введённый пользователем;
    - stored_hash: хэш из базы данных.

    Что возвращает:
    - True, если пароль верный;
    - False, если пароль неверный.
    """

    calculated_hash = hash_password(raw_password)
    return hmac.compare_digest(calculated_hash, stored_hash)