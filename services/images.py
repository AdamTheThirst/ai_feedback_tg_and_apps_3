# services/images.py

"""
Сервис работы с изображениями.

Отвечает за:
- отправку изображения в чат по img_id или img_path;
- кэширование Telegram file_id в БД;
- сохранение пользовательского изображения из Telegram в папку imgs.

Как работает:
- если есть img_id, отправляет фото по нему;
- если img_id нет, но есть img_path, отправляет фото с диска и сохраняет новый img_id;
- при добавлении нового промта умеет скачивать фото из Telegram на диск.

Что принимает:
- bot;
- chat_id;
- промт;
- данные фото.

Что возвращает:
- путь к изображению или ничего.
"""

from pathlib import Path
import logging

from aiogram import Bot
from aiogram.types import FSInputFile

from database.models.game_prompt import GamePrompt
from database.repositories.game_prompt_repository import GamePromptRepository


logger = logging.getLogger(__name__)


async def send_prompt_image_to_chat(
    bot: Bot,
    chat_id: int,
    session,
    prompt: GamePrompt,
) -> None:
    """
    Отправляет изображение промта в чат, если оно есть.

    Как работает:
    - если заполнено img_id, отправляет фото по file_id;
    - если img_id пуст, но заполнен img_path и файл существует,
      отправляет фото с диска и сохраняет полученный Telegram file_id в img_id;
    - если изображения нет, ничего не делает.

    Что принимает:
    - bot: объект Telegram-бота;
    - chat_id: id чата;
    - session: активная SQLAlchemy-сессия;
    - prompt: объект GamePrompt.

    Что возвращает:
    - ничего.
    """

    if prompt.img_id:
        await bot.send_photo(chat_id=chat_id, photo=prompt.img_id)
        return

    if not prompt.img_path:
        return

    file_path = Path(prompt.img_path)
    if not file_path.exists():
        logger.warning("Файл изображения не найден: %s", file_path)
        return

    sent_message = await bot.send_photo(
        chat_id=chat_id,
        photo=FSInputFile(str(file_path)),
    )

    if sent_message.photo:
        telegram_file_id = sent_message.photo[-1].file_id
        repo = GamePromptRepository(session)
        await repo.update_image_data(
            alias=prompt.alias,
            img_path=str(file_path.resolve()),
            img_id=telegram_file_id,
        )


async def save_telegram_photo(
    bot: Bot,
    telegram_file_id: str,
    filename_base: str,
) -> str:
    """
    Скачивает фото из Telegram в локальную папку imgs.

    Как работает:
    - создаёт папку imgs, если её ещё нет;
    - получает файл через Telegram API;
    - сохраняет его как jpg;
    - возвращает абсолютный путь.

    Что принимает:
    - bot: объект Telegram-бота;
    - telegram_file_id: file_id фотографии;
    - filename_base: базовое имя файла.

    Что возвращает:
    - абсолютный путь к сохранённому файлу.
    """

    imgs_dir = Path("imgs")
    imgs_dir.mkdir(parents=True, exist_ok=True)

    file_path = imgs_dir / f"{filename_base}.jpg"
    telegram_file = await bot.get_file(telegram_file_id)
    await bot.download(file=telegram_file, destination=file_path)

    return str(file_path.resolve())