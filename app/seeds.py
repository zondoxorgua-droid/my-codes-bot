"""Сидовые группы и категории, создаются при первом запуске."""
from __future__ import annotations

from app import db


SEEDS: dict[str, list[str]] = {
    "Roblox": [
        "200 Robux", "300 Robux", "400 Robux", "500 Robux",
        "600 Robux", "700 Robux", "800 Robux", "900 Robux", "1000 Robux",
    ],
    "Apple": [
        "2$", "3$", "4$", "5$", "6$", "7$", "8$", "9$", "10$",
    ],
    "Overwatch": [
        "200 монет", "500 монет", "1000 монет",
    ],
}


async def ensure_seeds() -> None:
    """Создаёт стартовый набор групп/категорий, если их ещё нет.

    Безопасно вызывать повторно: используется ON CONFLICT DO NOTHING.
    """
    for group_name, cats in SEEDS.items():
        group_id = await db.create_group(group_name)
        for cat_name in cats:
            await db.create_category(group_id, cat_name)
