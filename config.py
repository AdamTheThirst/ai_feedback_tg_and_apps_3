# config.py

"""
Модуль конфигурации приложения.

Отвечает за:
- загрузку переменных окружения из файла .env;
- хранение настроек проекта в одном месте;
- предоставление единого объекта settings.

Как работает:
- при импорте модуля выполняется загрузка .env;
- значения читаются через os.getenv;
- создаётся объект Settings, который используется в остальных модулях.

Что принимает:
- значения из файла .env.

Что возвращает:
- объект Settings с настройками приложения.
"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class Settings:
    """
    Класс с настройками приложения.

    Отвечает за:
    - хранение токена Telegram-бота;
    - хранение токена ИИ-сервиса;
    - хранение строки подключения к базе данных;
    - хранение pepper для хэширования паролей.

    Как работает:
    - создаётся один раз на уровне модуля;
    - затем используется по всему приложению.

    Что принимает:
    - значения из переменных окружения.

    Что возвращает:
    - типизированный объект настроек.
    """

    bot_token: str
    ai_api_token: str
    database_url: str
    password_pepper: str


settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", ""),
    ai_api_token=os.getenv("AI_API_TOKEN", ""),
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db"),
    password_pepper=os.getenv("PASSWORD_PEPPER", "dev_pepper_change_me"),
)