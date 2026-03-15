# database/models/__init__.py

"""
Пакетный модуль моделей.

Отвечает за:
- удобный импорт всех моделей в одном месте;
- регистрацию моделей в metadata SQLAlchemy.

Как работает:
- импортирует все ORM-модели проекта, которые должны участвовать в create_all.

Что принимает:
- ничего.

Что возвращает:
- набор импортированных моделей.
"""

from database.models.admin_login_incident import AdminLoginIncident
from database.models.analytics_prompt import AnalyticsPrompt
from database.models.app_log import AppLog
from database.models.deleted_prompt import DeletedPrompt
from database.models.dialog_message import DialogMessage
from database.models.game import Game
from database.models.game_prompt import GamePrompt
from database.models.password import Password
from database.models.ui_text import UIText
from database.models.user import User
from database.models.user_result import UserResult

__all__ = [
    "AdminLoginIncident",
    "AnalyticsPrompt",
    "AppLog",
    "DeletedPrompt",
    "DialogMessage",
    "Game",
    "GamePrompt",
    "Password",
    "UIText",
    "User",
    "UserResult",
]