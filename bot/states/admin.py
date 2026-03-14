# bot/states/admin.py

"""
FSM-состояния для админки.

Отвечает за:
- управление сценарием входа в админку;
- управление редактированием текстов;
- управление сменой пароля;
- управление разделом работы с промтами и играми;
- управление разделом аналитики.

Как работает:
- каждое состояние соответствует конкретному шагу сценария в админке.

Что принимает:
- ничего.

Что возвращает:
- класс состояний AdminStates.
"""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """
    Состояния FSM для административного раздела.

    Отвечает за:
    - шаги авторизации в админке;
    - шаги редактирования текстов;
    - шаги изменения административного пароля;
    - шаги добавления и удаления игр;
    - шаги добавления, изменения и удаления игровых промтов;
    - шаги раздела аналитики.

    Как работает:
    - каждое состояние используется соответствующим handler'ом;
    - состояние меняется по мере продвижения пользователя по сценарию.

    Что принимает:
    - ничего.

    Что возвращает:
    - набор состояний для FSM.
    """

    waiting_password = State()
    main_menu = State()
    tools_menu = State()
    analytics_menu = State()

    waiting_new_start_greeting = State()
    waiting_new_admin_greeting = State()
    waiting_new_button_text = State()

    waiting_current_password = State()
    waiting_new_password = State()
    waiting_new_password_confirm = State()

    waiting_new_game_name = State()

    waiting_new_prompt_button_name = State()
    waiting_new_prompt_conditions = State()
    waiting_new_prompt_text = State()
    waiting_new_prompt_image = State()

    waiting_edit_prompt_name = State()
    waiting_edit_prompt_conditions = State()
    waiting_edit_prompt_text = State()
    waiting_edit_prompt_image = State()

    waiting_delete_prompt_confirm = State()
    waiting_delete_game_confirm = State()

    waiting_new_analytics_game = State()
    waiting_new_analytics_prompt = State()

    waiting_edit_analytics_select = State()
    waiting_edit_analytics_prompt = State()

    waiting_delete_analytics_select = State()
    waiting_delete_analytics_confirm = State()
