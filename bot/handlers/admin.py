# bot/handlers/admin.py

"""
Обработчики административного раздела.

Отвечают за:
- вход в админку по паролю;
- допуск в админку только для конкретного user_id;
- вход в гостевой режим по специальному паролю;
- фиксацию инцидентов несанкционированного входа;
- показ главного меню админки;
- редактирование приветствия стартового экрана;
- редактирование приветствия админки;
- редактирование текстов кнопок;
- смену пароля администратора;
- выход из админки.

Как работает:
- использует FSM для пошаговых сценариев;
- получает и обновляет данные через репозитории;
- использует inline-клавиатуры;
- в гостевом режиме даёт просматривать админку, но не сохраняет изменения.

Что принимает:
- сообщения Telegram;
- callback-запросы Telegram;
- FSMContext;
- сессию базы данных.

Что возвращает:
- ничего.
"""

from html import escape
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.start import send_start_screen
from bot.keyboards.admin_keyboards import (
    build_admin_main_keyboard,
    build_buttons_list_keyboard,
    build_confirm_keyboard,
)
from bot.states.admin import AdminStates
from database.repositories.admin_login_incident_repository import (
    AdminLoginIncidentRepository,
)
from database.repositories.password_repository import PasswordRepository
from database.repositories.ui_text_repository import UITextRepository
from services.app_logger import AppLogger
from services.security import hash_password, verify_password


router = Router(name="admin-router")
logger = logging.getLogger(__name__)

ADMIN_USER_ID = 467116941
GUEST_ADMIN_PASSWORD = "111111"
GUEST_ADMIN_GREETING = "Это гостевой сеанс. Доступен просмотр, не доступны изменения"
GUEST_ADMIN_SAVE_BLOCK_MESSAGE = "Гостевой режим: изменения не сохранены."


async def is_guest_admin_session(state: FSMContext) -> bool:
    """
    Проверяет, находится ли пользователь в гостевом сеансе админки.

    Отвечает за:
    - чтение признака гостевого режима из FSMContext.

    Как работает:
    - забирает данные из FSMContext;
    - возвращает True, если в данных установлен флаг гостевого режима.

    Что принимает:
    - state: объект FSMContext.

    Что возвращает:
    - True, если это гостевой сеанс;
    - False в остальных случаях.
    """

    data = await state.get_data()
    return bool(data.get("is_guest_admin", False))


async def send_admin_main_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Отправляет пользователю главное меню админки.

    Отвечает за:
    - перевод пользователя в главное состояние админки;
    - получение приветствия админки;
    - получение текстов кнопок меню;
    - отправку сообщения с inline-клавиатурой;
    - показ специального приветствия в гостевом режиме.

    Как работает:
    - устанавливает состояние AdminStates.main_menu;
    - читает нужные тексты из таблицы ui_texts;
    - формирует клавиатуру;
    - если сеанс гостевой, показывает специальное сообщение вместо обычного приветствия;
    - отправляет меню пользователю.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.set_state(AdminStates.main_menu)

    ui_repo = UITextRepository(session)
    aliases = [
        "admin_greeting",
        "admin_button_edit_start_greeting",
        "admin_button_edit_admin_greeting",
        "admin_button_edit_buttons",
        "admin_button_change_password",
        "admin_button_exit",
    ]
    texts = await ui_repo.get_many_by_aliases(aliases)

    guest_mode = await is_guest_admin_session(state)

    greeting_text = texts["admin_greeting"].value
    if guest_mode:
        greeting_text = GUEST_ADMIN_GREETING

    keyboard = build_admin_main_keyboard(
        {
            "admin_button_edit_start_greeting": texts["admin_button_edit_start_greeting"].value,
            "admin_button_edit_admin_greeting": texts["admin_button_edit_admin_greeting"].value,
            "admin_button_edit_buttons": texts["admin_button_edit_buttons"].value,
            "admin_button_change_password": texts["admin_button_change_password"].value,
            "admin_button_exit": texts["admin_button_exit"].value,
        }
    )

    await message.answer(escape(greeting_text), reply_markup=keyboard)


async def send_text_preview_screen(
    message: Message,
    session: AsyncSession,
    text_alias: str,
    edit_callback: str,
) -> None:
    """
    Показывает текущий текст и кнопки "Изменить" / "Отмена".

    Отвечает за:
    - единый сценарий предпросмотра текста перед редактированием.

    Как работает:
    - получает текущий текст по alias;
    - получает подписи универсальных кнопок;
    - отправляет сообщение с предпросмотром и клавиатурой.

    Что принимает:
    - message: сообщение, через которое отправляется ответ;
    - session: активная сессия базы данных;
    - text_alias: alias текста, который будет редактироваться;
    - edit_callback: callback_data для кнопки "Изменить".

    Что возвращает:
    - ничего.
    """

    ui_repo = UITextRepository(session)
    current_text = await ui_repo.get_by_alias(text_alias)
    common_texts = await ui_repo.get_many_by_aliases(
        ["common_edit_button", "common_cancel_button"]
    )

    text_value = current_text.value if current_text is not None else "Текст не найден"
    keyboard = build_confirm_keyboard(
        edit_text=common_texts["common_edit_button"].value,
        cancel_text=common_texts["common_cancel_button"].value,
        edit_callback=edit_callback,
    )

    await message.answer(
        f"Текущий текст:\n{escape(text_value)}",
        reply_markup=keyboard,
    )


async def register_unauthorized_admin_attempt(
    message: Message,
    session: AsyncSession,
) -> None:
    """
    Фиксирует инцидент несанкционированного входа в админку.

    Отвечает за:
    - запись попытки входа с правильным паролем, но с неправильным user_id.

    Как работает:
    - берёт данные пользователя из объекта Telegram;
    - создаёт запись в таблице admin_login_incidents;
    - пишет технический лог.

    Что принимает:
    - message: входящее сообщение Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    if message.from_user is None:
        return

    incident_repo = AdminLoginIncidentRepository(session)

    # Telegram Bot API не предоставляет надёжной информации об устройстве пользователя.
    device = None

    await incident_repo.create_incident(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        device=device,
    )

    await AppLogger.warning(
        event="admin.unauthorized_login_attempt",
        source=__name__,
        message="Попытка несанкционированного входа в админку",
        payload={
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "device": device,
        },
        write_to_db=True,
    )


@router.message(Command("admin"))
async def admin_command_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает команду /admin.

    Отвечает за:
    - запуск сценария входа в админку;
    - создание записи пароля для административного user_id при первом входе;
    - перевод пользователя в состояние ожидания пароля;
    - сброс старых данных админского сеанса.

    Как работает:
    - очищает текущее состояние;
    - создаёт запись в passwords для ADMIN_USER_ID, если её ещё нет;
    - дефолтный пароль равен 123 и хранится в виде хэша;
    - затем просит пользователя ввести пароль.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await state.clear()

    password_repo = PasswordRepository(session)
    await password_repo.get_or_create(
        user_id=ADMIN_USER_ID,
        default_password_hash=hash_password("123"),
    )

    await AppLogger.info(
        event="admin.login_requested",
        source=__name__,
        message="Запрошен вход в админку",
        payload={
            "user_id": message.from_user.id if message.from_user else None,
        },
        write_to_db=True,
    )

    await state.set_state(AdminStates.waiting_password)
    await message.answer("Введите пароль администратора:")


@router.message(AdminStates.waiting_password)
async def admin_password_input_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод пароля для входа в админку.

    Отвечает за:
    - проверку введённого пароля;
    - отдельный вход в гостевой режим по паролю 111111;
    - проверку Telegram user_id;
    - фиксацию инцидента при правильном пароле и неверном user_id;
    - перевод в админку при успехе;
    - возврат на старт при ошибке.

    Как работает:
    - если введён пароль гостевого режима, открывает админку в режиме только для просмотра;
    - иначе получает запись администратора из passwords по ADMIN_USER_ID;
    - сверяет введённый пароль с хэшем;
    - если пароль верный и user_id корректный, открывает обычную админку;
    - если пароль верный, но user_id неверный, пишет инцидент и возвращает на старт;
    - если пароль неверный, возвращает на старт.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    raw_password = (message.text or "").strip()

    if raw_password == GUEST_ADMIN_PASSWORD:
        await state.update_data(is_guest_admin=True)

        await AppLogger.info(
            event="admin.guest_login_success",
            source=__name__,
            message="Успешный вход в гостевой режим админки",
            payload={
                "user_id": message.from_user.id,
            },
            write_to_db=True,
        )

        await send_admin_main_menu(message, state, session)
        return

    password_repo = PasswordRepository(session)
    admin_password_row = await password_repo.get_by_user_id(ADMIN_USER_ID)

    if admin_password_row is None:
        await message.answer("Пароль администратора не найден.")
        await send_start_screen(message, state, session)
        return

    is_password_valid = verify_password(raw_password, admin_password_row.admin)

    if not is_password_valid:
        await AppLogger.warning(
            event="admin.login_failed_invalid_password",
            source=__name__,
            message="Введён неверный пароль админки",
            payload={
                "user_id": message.from_user.id,
            },
            write_to_db=True,
        )

        await message.answer("Неверный пароль. Возврат на стартовый экран.")
        await send_start_screen(message, state, session)
        return

    if message.from_user.id != ADMIN_USER_ID:
        await register_unauthorized_admin_attempt(message, session)
        await message.answer("Доступ запрещён. Попытка зафиксирована.")
        await send_start_screen(message, state, session)
        return

    await state.update_data(is_guest_admin=False)

    await AppLogger.info(
        event="admin.login_success",
        source=__name__,
        message="Успешный вход администратора",
        payload={
            "user_id": message.from_user.id,
        },
        write_to_db=True,
    )

    await send_admin_main_menu(message, state, session)


@router.callback_query(F.data == "admin:edit_start_greeting")
async def admin_preview_start_greeting_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Показывает текущее приветствие стартового экрана.

    Отвечает за:
    - предпросмотр текста start_greeting перед редактированием.

    Как работает:
    - отправляет текущий текст;
    - показывает кнопки "Изменить" и "Отмена".

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_text_preview_screen(
        message=callback.message,
        session=session,
        text_alias="start_greeting",
        edit_callback="admin:confirm_edit_start_greeting",
    )


@router.callback_query(F.data == "admin:edit_admin_greeting")
async def admin_preview_admin_greeting_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Показывает текущее приветствие админки.

    Отвечает за:
    - предпросмотр текста admin_greeting перед редактированием.

    Как работает:
    - отправляет текущий текст;
    - показывает кнопки "Изменить" и "Отмена".

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_text_preview_screen(
        message=callback.message,
        session=session,
        text_alias="admin_greeting",
        edit_callback="admin:confirm_edit_admin_greeting",
    )


@router.callback_query(F.data == "admin:confirm_edit_start_greeting")
async def admin_confirm_edit_start_greeting_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние ожидания нового текста стартового приветствия.

    Отвечает за:
    - запуск шага ввода нового start_greeting.

    Как работает:
    - устанавливает состояние waiting_new_start_greeting;
    - просит пользователя прислать новый текст.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_new_start_greeting)
    await callback.message.answer("Напишите новый текст")


@router.callback_query(F.data == "admin:confirm_edit_admin_greeting")
async def admin_confirm_edit_admin_greeting_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Переводит пользователя в состояние ожидания нового текста приветствия админки.

    Отвечает за:
    - запуск шага ввода нового admin_greeting.

    Как работает:
    - устанавливает состояние waiting_new_admin_greeting;
    - просит пользователя прислать новый текст.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_new_admin_greeting)
    await callback.message.answer("Напишите новый текст")


@router.message(AdminStates.waiting_new_start_greeting)
async def admin_new_start_greeting_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст для стартового приветствия.

    Отвечает за:
    - валидацию длины текста;
    - сохранение нового текста в БД в обычном режиме;
    - блокировку сохранения в гостевом режиме;
    - возврат в главное меню админки.

    Как работает:
    - если длина текста меньше 10 символов, не сохраняет его;
    - если сеанс гостевой, не пишет ничего в БД;
    - затем в любом случае возвращает пользователя в главное меню админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()
    guest_mode = await is_guest_admin_session(state)

    if len(new_text) >= 10:
        if guest_mode:
            await AppLogger.info(
                event="admin.guest_attempt_update_start_greeting",
                source=__name__,
                message="Гость попытался изменить стартовое приветствие",
                payload={
                    "user_id": message.from_user.id if message.from_user else None,
                    "new_text": new_text,
                },
                write_to_db=True,
            )
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            ui_repo = UITextRepository(session)
            await ui_repo.update_value("start_greeting", new_text)
            await message.answer("Текст обновлён.")
    else:
        await message.answer("Текст слишком короткий. Возвращаю в админку.")

    await send_admin_main_menu(message, state, session)


@router.message(AdminStates.waiting_new_admin_greeting)
async def admin_new_admin_greeting_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст для приветствия админки.

    Отвечает за:
    - валидацию длины текста;
    - сохранение нового текста в БД в обычном режиме;
    - блокировку сохранения в гостевом режиме;
    - возврат в главное меню админки.

    Как работает:
    - если длина текста меньше 10 символов, не сохраняет его;
    - если сеанс гостевой, не пишет ничего в БД;
    - затем в любом случае возвращает пользователя в главное меню админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()
    guest_mode = await is_guest_admin_session(state)

    if len(new_text) >= 10:
        if guest_mode:
            await AppLogger.info(
                event="admin.guest_attempt_update_admin_greeting",
                source=__name__,
                message="Гость попытался изменить приветствие админки",
                payload={
                    "user_id": message.from_user.id if message.from_user else None,
                    "new_text": new_text,
                },
                write_to_db=True,
            )
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            ui_repo = UITextRepository(session)
            await ui_repo.update_value("admin_greeting", new_text)
            await message.answer("Текст обновлён.")
    else:
        await message.answer("Текст слишком короткий. Возвращаю в админку.")

    await send_admin_main_menu(message, state, session)


@router.callback_query(F.data == "admin:edit_buttons")
async def admin_edit_buttons_list_handler(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """
    Показывает список всех кнопок системы для редактирования.

    Отвечает за:
    - вывод перечня всех кнопок из таблицы ui_texts;
    - предоставление пользователю выбора, какую кнопку менять.

    Как работает:
    - получает все записи типа button;
    - строит клавиатуру из этих кнопок;
    - внизу добавляет кнопку отмены.

    Что принимает:
    - callback: callback-запрос Telegram;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    ui_repo = UITextRepository(session)
    buttons = await ui_repo.get_all_buttons()
    common_texts = await ui_repo.get_many_by_aliases(["common_cancel_button"])

    keyboard = build_buttons_list_keyboard(
        buttons=buttons,
        cancel_text=common_texts["common_cancel_button"].value,
    )

    await callback.message.answer(
        "Выберите кнопку, текст которой хотите изменить:",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("admin:button_select:"))
async def admin_button_select_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает выбор кнопки для редактирования.

    Отвечает за:
    - запоминание alias выбранной кнопки;
    - перевод пользователя в состояние ожидания нового текста кнопки.

    Как работает:
    - извлекает alias из callback_data;
    - сохраняет alias в FSMContext;
    - просит пользователя ввести новый текст кнопки.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    selected_alias = callback.data.split("admin:button_select:", maxsplit=1)[1]

    ui_repo = UITextRepository(session)
    selected_button = await ui_repo.get_by_alias(selected_alias)
    current_value = selected_button.value if selected_button is not None else "Не найдено"

    await state.update_data(target_button_alias=selected_alias)
    await state.set_state(AdminStates.waiting_new_button_text)

    await callback.message.answer(
        f"Текущий текст кнопки:\n{escape(current_value)}\n\n"
        "Введите новый текст, от 2 до 30 символов"
    )


@router.message(AdminStates.waiting_new_button_text)
async def admin_new_button_text_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает новый текст выбранной кнопки.

    Отвечает за:
    - получение alias редактируемой кнопки из FSM;
    - валидацию длины текста;
    - сохранение нового текста кнопки в обычном режиме;
    - блокировку сохранения в гостевом режиме;
    - возврат в главное меню админки.

    Как работает:
    - читает target_button_alias из FSMContext;
    - если текст имеет длину от 2 до 30 символов, в обычном режиме сохраняет его;
    - если сеанс гостевой, ничего не сохраняет;
    - затем возвращает пользователя в главное меню админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()
    data = await state.get_data()
    button_alias = data.get("target_button_alias")
    guest_mode = await is_guest_admin_session(state)

    if button_alias is not None and 2 <= len(new_text) <= 30:
        if guest_mode:
            await AppLogger.info(
                event="admin.guest_attempt_update_button_text",
                source=__name__,
                message="Гость попытался изменить текст кнопки",
                payload={
                    "user_id": message.from_user.id if message.from_user else None,
                    "button_alias": button_alias,
                    "new_text": new_text,
                },
                write_to_db=True,
            )
            await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        else:
            ui_repo = UITextRepository(session)
            await ui_repo.update_value(button_alias, new_text)
            await message.answer("Текст кнопки обновлён.")
    else:
        await message.answer("Некорректная длина текста. Возвращаю в админку.")

    await state.update_data(target_button_alias=None)
    await send_admin_main_menu(message, state, session)


@router.callback_query(F.data == "admin:change_password")
async def admin_change_password_start_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Запускает сценарий изменения пароля админки.

    Отвечает за:
    - перевод пользователя в шаг ввода текущего пароля.

    Как работает:
    - устанавливает состояние waiting_current_password;
    - отправляет сообщение с инструкцией.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(AdminStates.waiting_current_password)
    await callback.message.answer("Изменение пароля\n\nВведите текущий пароль:")


@router.message(AdminStates.waiting_current_password)
async def admin_current_password_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает ввод текущего пароля при смене пароля.

    Отвечает за:
    - проверку текущего пароля в обычном режиме;
    - пропуск проверки в гостевом режиме, чтобы можно было пройти сценарий до конца;
    - защиту от несанкционированного изменения пароля;
    - перевод к вводу нового пароля при успехе;
    - возврат на старт при ошибке.

    Как работает:
    - если сеанс гостевой, сразу переводит пользователя к шагу ввода нового пароля;
    - иначе получает хэш административного пароля по ADMIN_USER_ID;
    - проверяет пароль;
    - если пароль корректен, но user_id не административный, пишет инцидент и уводит на старт;
    - если всё корректно, переводит к шагу ввода нового пароля.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    guest_mode = await is_guest_admin_session(state)
    if guest_mode:
        await state.set_state(AdminStates.waiting_new_password)
        await message.answer("Введите новый пароль:")
        return

    raw_password = (message.text or "").strip()
    password_repo = PasswordRepository(session)
    admin_password_row = await password_repo.get_by_user_id(ADMIN_USER_ID)

    if admin_password_row is None:
        await message.answer("Пароль администратора не найден.")
        await send_start_screen(message, state, session)
        return

    is_password_valid = verify_password(raw_password, admin_password_row.admin)

    if not is_password_valid:
        await message.answer("Текущий пароль неверный. Возврат на стартовый экран.")
        await send_start_screen(message, state, session)
        return

    if message.from_user.id != ADMIN_USER_ID:
        await register_unauthorized_admin_attempt(message, session)
        await message.answer("Доступ запрещён. Попытка зафиксирована.")
        await send_start_screen(message, state, session)
        return

    await state.set_state(AdminStates.waiting_new_password)
    await message.answer("Введите новый пароль:")


@router.message(AdminStates.waiting_new_password)
async def admin_new_password_handler(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает ввод нового пароля.

    Отвечает за:
    - временное сохранение нового пароля в FSM;
    - перевод на шаг подтверждения нового пароля.

    Как работает:
    - сохраняет введённое значение в FSMContext;
    - просит пользователя повторить новый пароль.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext.

    Что возвращает:
    - ничего.
    """

    new_password = (message.text or "").strip()
    await state.update_data(new_password=new_password)
    await state.set_state(AdminStates.waiting_new_password_confirm)
    await message.answer("Повторно введите новый пароль:")


@router.message(AdminStates.waiting_new_password_confirm)
async def admin_new_password_confirm_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Обрабатывает подтверждение нового пароля.

    Отвечает за:
    - сравнение двух вводов нового пароля;
    - сохранение нового хэша в БД в обычном режиме;
    - блокировку сохранения в гостевом режиме;
    - возврат в главное меню админки.

    Как работает:
    - получает ранее введённый пароль из FSMContext;
    - сравнивает его с повторным вводом;
    - при совпадении в обычном режиме сохраняет хэш в БД для ADMIN_USER_ID;
    - в гостевом режиме не сохраняет ничего;
    - затем возвращает пользователя в админку.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    data = await state.get_data()
    first_password = data.get("new_password", "")
    second_password = (message.text or "").strip()
    guest_mode = await is_guest_admin_session(state)

    if not first_password or first_password != second_password:
        await message.answer("Пароли не совпали. Возвращаю в админку.")
        await state.update_data(new_password=None)
        await send_admin_main_menu(message, state, session)
        return

    if guest_mode:
        await AppLogger.info(
            event="admin.guest_attempt_change_password",
            source=__name__,
            message="Гость попытался изменить пароль администратора",
            payload={
                "user_id": message.from_user.id if message.from_user else None,
            },
            write_to_db=True,
        )
        await state.update_data(new_password=None)
        await message.answer(GUEST_ADMIN_SAVE_BLOCK_MESSAGE)
        await send_admin_main_menu(message, state, session)
        return

    password_repo = PasswordRepository(session)
    await password_repo.update_password_hash(
        user_id=ADMIN_USER_ID,
        new_password_hash=hash_password(second_password),
    )

    await AppLogger.info(
        event="admin.password_changed",
        source=__name__,
        message="Пароль администратора изменён",
        payload={
            "user_id": message.from_user.id if message.from_user else None,
        },
        write_to_db=True,
    )

    await state.update_data(new_password=None)
    await message.answer("Пароль успешно изменён.")
    await send_admin_main_menu(message, state, session)


@router.callback_query(F.data == "admin:back_main")
async def admin_back_to_main_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Возвращает пользователя в главное меню админки.

    Отвечает за:
    - обработку нажатия кнопки "Отмена".

    Как работает:
    - отправляет главное меню админки повторно.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_admin_main_menu(callback.message, state, session)


@router.callback_query(F.data == "admin:exit")
async def admin_exit_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """
    Выводит пользователя из админки.

    Отвечает за:
    - выход из административного режима;
    - возврат на стартовый экран приложения.

    Как работает:
    - вызывает общую функцию send_start_screen.

    Что принимает:
    - callback: callback-запрос Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    await callback.answer()
    if callback.message is None:
        return

    await send_start_screen(callback.message, state, session)