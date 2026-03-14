# app/bot/states/admin.py

"""
Файл: app/bot/states/admin.py

FSM-состояния для админки.

Отвечает за:
- управление сценарием входа в админку;
- управление редактированием текстов;
- управление сменой пароля.

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
    - шаги изменения административного пароля.

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

    waiting_new_start_greeting = State()
    waiting_new_admin_greeting = State()
    waiting_new_button_text = State()

    waiting_current_password = State()
    waiting_new_password = State()
    waiting_new_password_confirm = State()