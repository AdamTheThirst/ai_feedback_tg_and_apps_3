# app/bot/handlers/admin.py

"""
Файл: app/bot/handlers/admin.py

Обработчики административного раздела.

Отвечает за:
- вход в админку по паролю;
- показ главного меню админки;
- редактирование приветствия стартового экрана;
- редактирование приветствия админки;
- редактирование текстов кнопок;
- смену пароля администратора;
- выход из админки.

Как работает:
- использует FSM для пошаговых сценариев;
- получает и обновляет данные через репозитории;
- использует inline-клавиатуры.

Что принимает:
- сообщения Telegram;
- callback-запросы Telegram;
- FSMContext;
- сессию базы данных.

Что возвращает:
- ничего.
"""

from html import escape

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
from database.repositories.password_repository import PasswordRepository
from database.repositories.ui_text_repository import UITextRepository
from services.security import hash_password, verify_password


router = Router(name="admin-router")


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
    - отправку сообщения с inline-клавиатурой.

    Как работает:
    - устанавливает состояние AdminStates.main_menu;
    - читает нужные тексты из таблицы ui_texts;
    - формирует клавиатуру;
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

    greeting_text = texts["admin_greeting"].value
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
        f"<b>Текущий текст:</b>\n{escape(text_value)}",
        reply_markup=keyboard,
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
    - создание дефолтного пароля пользователя при первом входе;
    - перевод пользователя в состояние ожидания пароля.

    Как работает:
    - создаёт запись в passwords, если её ещё нет;
    - дефолтный пароль равен 123 и хранится в виде хэша;
    - затем просит пользователя ввести пароль.

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

    password_repo = PasswordRepository(session)
    await password_repo.get_or_create(
        user_id=message.from_user.id,
        default_password_hash=hash_password("123"),
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
    - перевод в админку при успехе;
    - возврат на старт при ошибке.

    Как работает:
    - получает запись пользователя из passwords;
    - сверяет введённый пароль с хэшем;
    - при успехе показывает меню админки;
    - при ошибке показывает стартовый экран.

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

    password_repo = PasswordRepository(session)
    password_row = await password_repo.get_by_user_id(message.from_user.id)

    if password_row is None:
        await message.answer("Пароль не найден. Попробуйте ещё раз через /admin.")
        await state.clear()
        return

    if verify_password(raw_password, password_row.admin):
        await send_admin_main_menu(message, state, session)
        return

    await message.answer("Неверный пароль. Возврат на стартовый экран.")
    await send_start_screen(message, state, session)


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
    - сохранение нового текста в БД;
    - возврат в главное меню админки.

    Как работает:
    - если длина текста меньше 10 символов, не сохраняет его;
    - затем в любом случае возвращает пользователя в главное меню админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()

    if len(new_text) >= 10:
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
    - сохранение нового текста в БД;
    - возврат в главное меню админки.

    Как работает:
    - если длина текста меньше 10 символов, не сохраняет его;
    - затем в любом случае возвращает пользователя в главное меню админки.

    Что принимает:
    - message: входящее сообщение Telegram;
    - state: объект FSMContext;
    - session: активная сессия базы данных.

    Что возвращает:
    - ничего.
    """

    new_text = (message.text or "").strip()

    if len(new_text) >= 10:
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
        f"Текущий текст кнопки:\n<b>{escape(current_value)}</b>\n\n"
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
    - сохранение нового текста кнопки;
    - возврат в главное меню админки.

    Как работает:
    - читает target_button_alias из FSMContext;
    - если текст имеет длину от 2 до 30 символов, сохраняет его;
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

    if button_alias is not None and 2 <= len(new_text) <= 30:
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
    - проверку текущего пароля;
    - перевод к вводу нового пароля при успехе;
    - возврат на старт при ошибке.

    Как работает:
    - сверяет введённый пароль с хэшем в БД;
    - при успехе переводит в waiting_new_password;
    - при ошибке вызывает стартовый экран.

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
    password_repo = PasswordRepository(session)
    password_row = await password_repo.get_by_user_id(message.from_user.id)

    if password_row is None or not verify_password(raw_password, password_row.admin):
        await message.answer("Текущий пароль неверный. Возврат на стартовый экран.")
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
    - сохранение нового хэша в БД;
    - возврат в главное меню админки.

    Как работает:
    - получает ранее введённый пароль из FSMContext;
    - сравнивает его с повторным вводом;
    - при совпадении сохраняет хэш в БД;
    - затем возвращает пользователя в админку.

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

    data = await state.get_data()
    first_password = data.get("new_password", "")
    second_password = (message.text or "").strip()

    if not first_password or first_password != second_password:
        await message.answer("Пароли не совпали. Возвращаю в админку.")
        await state.update_data(new_password=None)
        await send_admin_main_menu(message, state, session)
        return

    password_repo = PasswordRepository(session)
    await password_repo.update_password_hash(
        user_id=message.from_user.id,
        new_password_hash=hash_password(second_password),
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