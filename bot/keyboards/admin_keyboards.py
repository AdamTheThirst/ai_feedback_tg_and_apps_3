# bot/keyboards/admin_keyboards.py

"""
Клавиатуры для админки.

Отвечает за:
- сборку inline-клавиатур административного меню;
- сборку клавиатур подтверждения;
- сборку списка всех кнопок системы для редактирования.

Как работает:
- принимает готовые тексты кнопок;
- формирует объекты InlineKeyboardMarkup.

Что принимает:
- словари текстов кнопок;
- список кнопок из базы.

Что возвращает:
- готовые inline-клавиатуры.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models.ui_text import UIText


def build_admin_main_keyboard(button_texts: dict[str, str]) -> InlineKeyboardMarkup:
    """
    Собирает основную клавиатуру админки.

    Отвечает за:
    - отображение главных действий административного меню.

    Как работает:
    - получает словарь alias -> текст кнопки;
    - создаёт inline-кнопки с фиксированными callback_data.

    Что принимает:
    - button_texts: словарь с текстами кнопок.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(
        text=button_texts["admin_button_edit_start_greeting"],
        callback_data="admin:edit_start_greeting",
    )
    builder.button(
        text=button_texts["admin_button_edit_admin_greeting"],
        callback_data="admin:edit_admin_greeting",
    )
    builder.button(
        text=button_texts["admin_button_edit_buttons"],
        callback_data="admin:edit_buttons",
    )
    builder.button(
        text=button_texts["admin_button_change_password"],
        callback_data="admin:change_password",
    )
    builder.button(
        text=button_texts["admin_button_exit"],
        callback_data="admin:exit",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_keyboard(
    edit_text: str,
    cancel_text: str,
    edit_callback: str,
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру подтверждения действия.

    Отвечает за:
    - вывод кнопок "Изменить" и "Отмена" для сценариев редактирования.

    Как работает:
    - принимает текст кнопок и callback для кнопки изменения;
    - callback отмены всегда возвращает в главное меню админки.

    Что принимает:
    - edit_text: текст кнопки подтверждения;
    - cancel_text: текст кнопки отмены;
    - edit_callback: callback_data для кнопки изменения.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(text=edit_text, callback_data=edit_callback)
    builder.button(text=cancel_text, callback_data="admin:back_main")
    builder.adjust(2)
    return builder.as_markup()


def build_buttons_list_keyboard(
    buttons: list[UIText],
    cancel_text: str,
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру со всеми кнопками системы.

    Отвечает за:
    - отображение списка всех редактируемых кнопок для выбора.

    Как работает:
    - для каждой кнопки из базы создаёт отдельную inline-кнопку;
    - в callback_data кладёт alias выбранной кнопки;
    - внизу добавляет кнопку отмены.

    Что принимает:
    - buttons: список кнопок из базы;
    - cancel_text: текст кнопки отмены.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()

    for item in buttons:
        builder.button(
            text=item.value,
            callback_data=f"admin:button_select:{item.alias}",
        )

    builder.button(text=cancel_text, callback_data="admin:back_main")
    builder.adjust(1)
    return builder.as_markup()