# bot/keyboards/main_keyboards.py

"""
Клавиатуры основного пользовательского интерфейса.

Отвечает за:
- сборку стартового меню;
- сборку меню игры;
- сборку кнопки завершения диалога.

Как работает:
- использует данные игр и UI-текстов;
- возвращает готовые inline-клавиатуры.

Что принимает:
- список игр;
- список игровых кнопок;
- текст кнопки завершения.

Что возвращает:
- InlineKeyboardMarkup.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models.game import Game
from database.models.ui_text import UIText


def build_start_menu_keyboard(
    games: list[Game],
    encyclopedia_text: str,
    profile_text: str,
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру стартового меню.

    Как работает:
    - верхний уровень игр строится по таблице games;
    - затем добавляются две временные кнопки-заглушки.

    Что принимает:
    - games: список игр;
    - encyclopedia_text: текст кнопки Энциклопедия;
    - profile_text: текст кнопки Личный кабинет.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()

    for item in games:
        builder.button(
            text=item.name,
            callback_data=f"main:game_root:{item.game_id}",
        )

    builder.button(text=encyclopedia_text, callback_data="main:stub:encyclopedia")
    builder.button(text=profile_text, callback_data="main:stub:profile")
    builder.adjust(1)

    return builder.as_markup()


def build_game_menu_keyboard(second_level_buttons: list[UIText]) -> InlineKeyboardMarkup | None:
    """
    Собирает клавиатуру меню конкретной игры.

    Как работает:
    - для каждой кнопки второго уровня создаёт inline-кнопку;
    - в callback_data сохраняет game_id и alias UI-кнопки.

    Что принимает:
    - second_level_buttons: список кнопок второго уровня.

    Что возвращает:
    - объект InlineKeyboardMarkup или None, если кнопок нет.
    """

    if not second_level_buttons:
        return None

    builder = InlineKeyboardBuilder()

    for item in second_level_buttons:
        builder.button(
            text=item.value,
            callback_data=f"game:start:{item.game}:{item.alias}",
        )

    builder.adjust(1)
    return builder.as_markup()


def build_finish_dialog_keyboard(button_text: str) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру с кнопкой завершения диалога.

    Что принимает:
    - button_text: текст кнопки.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()
    builder.button(text=button_text, callback_data="game:finish_feedback")
    builder.adjust(1)
    return builder.as_markup()