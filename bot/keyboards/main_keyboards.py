# bot/keyboards/main_keyboards.py

"""
Клавиатуры основного пользовательского интерфейса.

Отвечает за:
- сборку стартового меню;
- сборку игровых меню.

Как работает:
- принимает тексты и записи кнопок из базы;
- формирует inline-клавиатуры.

Что принимает:
- игровые кнопки из БД;
- тексты статичных кнопок.

Что возвращает:
- готовые inline-клавиатуры.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models.ui_text import UIText


def build_start_menu_keyboard(
    first_level_game_buttons: list[UIText],
    encyclopedia_text: str,
    profile_text: str,
) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру стартового экрана.

    Отвечает за:
    - отображение кнопок верхнего уровня;
    - добавление игровых кнопок, которые строятся динамически;
    - добавление неактивных заглушек Энциклопедия и Личный кабинет.

    Как работает:
    - сначала добавляет игровые кнопки первого уровня;
    - затем добавляет две кнопки-заглушки.

    Что принимает:
    - first_level_game_buttons: список игровых кнопок верхнего уровня;
    - encyclopedia_text: текст кнопки Энциклопедия;
    - profile_text: текст кнопки Личный кабинет.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()

    for item in first_level_game_buttons:
        builder.button(
            text=item.value,
            callback_data=f"main:game_root:{item.game}",
        )

    builder.button(text=encyclopedia_text, callback_data="main:stub:encyclopedia")
    builder.button(text=profile_text, callback_data="main:stub:profile")
    builder.adjust(1)

    return builder.as_markup()


def build_game_menu_keyboard(second_level_buttons: list[UIText]) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру игрового меню второго уровня.

    Отвечает за:
    - отображение списка сценариев выбранной игры.

    Как работает:
    - для каждой записи из БД создаёт отдельную inline-кнопку;
    - в callback_data кладёт игру и alias выбранной кнопки.

    Что принимает:
    - second_level_buttons: список игровых кнопок второго уровня.

    Что возвращает:
    - объект InlineKeyboardMarkup.
    """

    builder = InlineKeyboardBuilder()

    for item in second_level_buttons:
        builder.button(
            text=item.value,
            callback_data=f"game:start:{item.game}:{item.alias}",
        )

    builder.adjust(1)
    return builder.as_markup()