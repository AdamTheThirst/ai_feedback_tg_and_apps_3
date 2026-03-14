# bot/keyboards/admin_keyboards.py

"""
Клавиатуры для админки.

Отвечает за:
- сборку inline-клавиатур административного меню;
- сборку клавиатуры раздела работы с промтами и играми;
- сборку клавиатуры списка игр;
- сборку клавиатур подтверждения;
- сборку списка всех кнопок системы для редактирования.

Как работает:
- принимает готовые тексты кнопок;
- формирует объекты InlineKeyboardMarkup.

Что принимает:
- словари текстов кнопок;
- список кнопок из базы;
- список игр из базы.

Что возвращает:
- готовые inline-клавиатуры.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models.game import Game
from database.models.ui_text import UIText


def build_admin_main_keyboard(button_texts: dict[str, str]) -> InlineKeyboardMarkup:
    """
    Собирает основную клавиатуру админки.

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
        text=button_texts["admin_button_prompt_games_work"],
        callback_data="admin:tools_menu",
    )
    builder.button(
        text=button_texts["admin_button_exit"],
        callback_data="admin:exit",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_admin_tools_keyboard(button_texts: dict[str, str]) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру раздела работы с промтами и играми.

    Что принимает:
    - button_texts: словарь с текстами кнопок.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(
        text=button_texts["admin_button_tools_add_game"],
        callback_data="admin:add_game",
    )
    builder.button(
        text=button_texts["admin_button_tools_add_prompt"],
        callback_data="admin:add_prompt",
    )
    builder.button(
        text=button_texts["admin_button_tools_edit_prompts"],
        callback_data="admin:edit_prompts",
    )
    builder.button(
        text=button_texts["admin_button_tools_toggle_prompt"],
        callback_data="admin:toggle_prompt",
    )
    builder.button(
        text=button_texts["admin_button_tools_delete_prompt"],
        callback_data="admin:delete_prompt",
    )
    builder.button(
        text=button_texts["admin_button_tools_delete_game"],
        callback_data="admin:delete_game",
    )
    builder.button(
        text=button_texts["admin_button_tools_back"],
        callback_data="admin:back_main",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_games_list_keyboard(
    games: list[Game],
    cancel_text: str,
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру списка игр.

    Что принимает:
    - games: список игр;
    - cancel_text: текст кнопки возврата.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()

    for game in games:
        builder.button(
            text=game.name,
            callback_data=f"admin:delete_game_select:{game.game_id}",
        )

    builder.button(text=cancel_text, callback_data="admin:back_main")
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_keyboard(
    edit_text: str,
    cancel_text: str,
    edit_callback: str,
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру подтверждения действия.

    Что принимает:
    - edit_text: текст кнопки подтверждения;
    - cancel_text: текст кнопки отмены;
    - edit_callback: callback_data для кнопки подтверждения.

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