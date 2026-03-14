# app/database/models/__init__.py

"""
Файл: app/database/models/__init__.py

Пакетный модуль моделей.

Отвечает за:
- удобный импорт всех моделей в одном месте;
- регистрацию моделей перед созданием таблиц.

Как работает:
- импортирует все модели, которые должны попасть в metadata SQLAlchemy.

Что принимает:
- ничего.

Что возвращает:
- набор импортированных моделей.
"""

from database.models.password import Password
from database.models.ui_text import UIText

__all__ = ["Password", "UIText"]