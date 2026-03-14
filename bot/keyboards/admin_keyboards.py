# bot/keyboards/admin_keyboards.py

"""
Клавиатуры для админки.

Отвечает за:
- сборку inline-клавиатур административного меню;
- сборку клавиатуры раздела работы с промтами и играми;
- сборку клавиатуры раздела аналитики;
- сборку клавиатуры списка игр;
- сборку клавиатуры списка промтов;
- сборку клавиатуры действий редактирования промта;
- сборку клавиатур подтверждения;
- сборку клавиатуры пропуска изображения;
- сборку клавиатуры после создания аналитики;
- сборку списка всех кнопок системы для редактирования.

Как работает:
- принимает готовые тексты кнопок;
- формирует объекты InlineKeyboardMarkup.

Что принимает:
- словари текстов кнопок;
- списки сущностей из базы.

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
        text=button_texts["admin_button_analytics"],
        callback_data="admin:analytics_menu",
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


def build_admin_analytics_keyboard(button_texts: dict[str, str]) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру раздела аналитики.

    Что принимает:
    - button_texts: словарь с текстами кнопок.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(
        text=button_texts["admin_button_analytics_new"],
        callback_data="admin:new_analytics",
    )
    builder.button(
        text=button_texts["admin_button_analytics_edit"],
        callback_data="admin:edit_analytics",
    )
    builder.button(
        text=button_texts["admin_button_analytics_delete"],
        callback_data="admin:delete_analytics",
    )
    builder.button(
        text=button_texts["admin_button_analytics_back"],
        callback_data="admin:back_main",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_games_selection_keyboard(
    games: list[Game],
    cancel_text: str,
    callback_prefix: str,
    cancel_callback: str = "admin:back_main",
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру списка игр.

    Что принимает:
    - games: список игр;
    - cancel_text: текст кнопки возврата;
    - callback_prefix: префикс callback_data;
    - cancel_callback: callback_data кнопки отмены.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()

    for game in games:
        builder.button(
            text=game.name,
            callback_data=f"{callback_prefix}:{game.game_id}",
        )

    builder.button(text=cancel_text, callback_data=cancel_callback)
    builder.adjust(1)
    return builder.as_markup()


def build_prompt_selection_keyboard(
    items: list[tuple[str, str]],
    cancel_text: str,
    callback_prefix: str,
    cancel_callback: str = "admin:back_main",
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру списка промтов или аналитик.

    Что принимает:
    - items: список кортежей (текст кнопки, ключ);
    - cancel_text: текст кнопки возврата;
    - callback_prefix: префикс callback_data;
    - cancel_callback: callback_data кнопки отмены.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()

    for text, key in items:
        builder.button(
            text=text,
            callback_data=f"{callback_prefix}:{key}",
        )

    builder.button(text=cancel_text, callback_data=cancel_callback)
    builder.adjust(1)
    return builder.as_markup()


def build_prompt_edit_actions_keyboard(button_texts: dict[str, str]) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру действий редактирования промта.

    Что принимает:
    - button_texts: словарь с текстами кнопок.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(
        text=button_texts["admin_button_prompt_action_name"],
        callback_data="admin:prompt_action_name",
    )
    builder.button(
        text=button_texts["admin_button_prompt_action_conditions"],
        callback_data="admin:prompt_action_conditions",
    )
    builder.button(
        text=button_texts["admin_button_prompt_action_prompt"],
        callback_data="admin:prompt_action_prompt",
    )
    builder.button(
        text=button_texts["admin_button_prompt_action_image"],
        callback_data="admin:prompt_action_image",
    )
    builder.button(
        text=button_texts["common_cancel_button"],
        callback_data="admin:tools_menu",
    )
    builder.adjust(1)
    return builder.as_markup()


def build_skip_image_keyboard(skip_text: str, cancel_text: str) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру пропуска загрузки изображения.

    Что принимает:
    - skip_text: текст кнопки пропуска;
    - cancel_text: текст кнопки отмены.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(text=skip_text, callback_data="admin:prompt_skip_image")
    builder.button(text=cancel_text, callback_data="admin:back_main")
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_keyboard(
    edit_text: str,
    cancel_text: str,
    edit_callback: str,
    cancel_callback: str = "admin:back_main",
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру подтверждения действия.

    Что принимает:
    - edit_text: текст кнопки подтверждения;
    - cancel_text: текст кнопки отмены;
    - edit_callback: callback_data для кнопки подтверждения;
    - cancel_callback: callback_data для кнопки отмены.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(text=edit_text, callback_data=edit_callback)
    builder.button(text=cancel_text, callback_data=cancel_callback)
    builder.adjust(2)
    return builder.as_markup()


def build_post_create_analytics_keyboard(
    add_more_text: str,
    back_text: str,
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру после успешного создания аналитического промта.

    Что принимает:
    - add_more_text: текст кнопки добавления ещё одного промта;
    - back_text: текст кнопки возврата назад.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(
        text=add_more_text,
        callback_data="admin:analytics_add_one_more",
    )
    builder.button(
        text=back_text,
        callback_data="admin:analytics_menu",
    )
    builder.adjust(1)
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
