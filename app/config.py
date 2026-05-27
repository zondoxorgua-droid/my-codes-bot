"""Настройки бота. Читаются из .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

_root_admin_raw = os.getenv("ROOT_ADMIN_ID", "0").strip()
try:
    ROOT_ADMIN_ID: int = int(_root_admin_raw)
except ValueError:
    ROOT_ADMIN_ID = 0

DB_PATH: str = os.getenv("DB_PATH", "data/codes.db").strip()

# Лимит на количество кодов, которые можно выдать за один раз (защита от опечаток)
MAX_TAKE_PER_REQUEST: int = int(os.getenv("MAX_TAKE_PER_REQUEST", "500"))

# Если кодов в одной выдаче больше этого порога — отдаём файлом, иначе сообщением
TEXT_OUTPUT_THRESHOLD: int = int(os.getenv("TEXT_OUTPUT_THRESHOLD", "20"))


def validate() -> None:
    """Проверить, что критичные переменные заданы."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в .env")
    if ROOT_ADMIN_ID <= 0:
        raise RuntimeError("ROOT_ADMIN_ID не задан в .env")

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
