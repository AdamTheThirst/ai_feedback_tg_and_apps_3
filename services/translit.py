# services/translit.py

"""
Сервис транслитерации и подготовки slug.

Отвечает за:
- транслитерацию русского текста в латиницу;
- преобразование строки в безопасный slug для alias.

Как работает:
- заменяет русские символы на латинские;
- приводит строку к нижнему регистру;
- заменяет пробелы и разделители на underscore;
- удаляет лишние символы.

Что принимает:
- произвольную строку.

Что возвращает:
- slug в нижнем регистре.
"""

import re


TRANSLIT_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def slugify_text(value: str) -> str:
    """
    Преобразует строку в slug.

    Как работает:
    - транслитерирует кириллицу;
    - заменяет пробелы и разделители на underscore;
    - оставляет только латиницу, цифры и underscore;
    - убирает повторяющиеся underscore.

    Что принимает:
    - value: исходная строка.

    Что возвращает:
    - slug в нижнем регистре.
    """

    source = value.strip().lower()

    normalized: list[str] = []
    for char in source:
        if char in TRANSLIT_MAP:
            normalized.append(TRANSLIT_MAP[char])
        elif char.isalnum():
            normalized.append(char)
        else:
            normalized.append("_")

    slug = "".join(normalized)
    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")

    if not slug:
        return "item"

    return slug