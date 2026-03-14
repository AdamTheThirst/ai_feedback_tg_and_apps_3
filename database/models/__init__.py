# database/models/__init__.py

"""
Пакетный модуль моделей.

Отвечает за:
- удобный импорт всех моделей из одного места;
- регистрацию моделей в metadata SQLAlchemy перед созданием таблиц.

Как работает:
- импортирует все ORM-модели, которые должны участвовать в create_all.

Что принимает:
- ничего.

Что возвращает:
- набор импортированных моделей.
"""

from database.models.admin_login_incident import AdminLoginIncident
from database.models.password import Password
from database.models.ui_text import UIText

__all__ = ["AdminLoginIncident", "Password", "UIText"]