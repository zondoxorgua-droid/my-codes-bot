"""Слой работы с SQLite. Чистые async-функции, без ORM."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from app.config import DB_PATH

# ---------- SCHEMA ----------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    role       TEXT NOT NULL DEFAULT 'user',  -- 'admin' | 'user'
    added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS groups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id   INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_id, name)
);

CREATE TABLE IF NOT EXISTS codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    code        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'available',  -- 'available' | 'taken'
    taken_by    INTEGER,
    taken_at    TIMESTAMP,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_id, code)
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    count       INTEGER NOT NULL,
    codes       TEXT,                                  -- сами выданные коды, по одному на строку
    taken_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_codes_cat_status ON codes(category_id, status);
CREATE INDEX IF NOT EXISTS idx_tx_user_time     ON transactions(user_id, taken_at DESC);
"""


# ---------- DATA CLASSES ----------

@dataclass(frozen=True)
class User:
    user_id: int
    username: Optional[str]
    role: str
    added_at: str


@dataclass(frozen=True)
class Group:
    id: int
    name: str


@dataclass(frozen=True)
class Category:
    id: int
    group_id: int
    name: str
    available: int = 0  # заполняется через JOIN при получении списков


@dataclass(frozen=True)
class TransactionRow:
    id: int
    group_name: str
    category_name: str
    count: int
    taken_at: str
    codes: str = ""  # сами коды, по одному на строку


# ---------- INIT ----------

async def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(SCHEMA)
        await _migrate(db)
        await db.commit()


async def _migrate(db: aiosqlite.Connection) -> None:
    """Лёгкие миграции для уже существующих баз."""
    # transactions.codes — добавлен позже, чтобы хранить сами выданные коды
    async with db.execute("PRAGMA table_info(transactions)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    if "codes" not in cols:
        await db.execute("ALTER TABLE transactions ADD COLUMN codes TEXT")


def _connect() -> aiosqlite.Connection:
    """Хелпер: всегда включаем foreign_keys."""
    return aiosqlite.connect(DB_PATH)


# ---------- USERS ----------

async def upsert_user(user_id: int, username: Optional[str]) -> None:
    """Создать запись о пользователе, если ещё нет. Не меняет роль."""
    async with _connect() as db:
        await db.execute(
            "INSERT INTO users(user_id, username) VALUES(?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username),
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[User]:
    async with _connect() as db:
        async with db.execute(
            "SELECT user_id, username, role, added_at FROM users WHERE user_id=?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return User(*row)


async def list_users() -> list[User]:
    async with _connect() as db:
        async with db.execute(
            "SELECT user_id, username, role, added_at FROM users ORDER BY added_at"
        ) as cur:
            return [User(*r) for r in await cur.fetchall()]


async def set_user_role(user_id: int, role: str, username: Optional[str] = None) -> None:
    assert role in ("admin", "user")
    async with _connect() as db:
        await db.execute(
            "INSERT INTO users(user_id, username, role) VALUES(?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, "
            "  username=COALESCE(excluded.username, users.username)",
            (user_id, username, role),
        )
        await db.commit()


async def delete_user(user_id: int) -> None:
    async with _connect() as db:
        await db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        await db.commit()


# ---------- GROUPS ----------

async def create_group(name: str) -> int:
    async with _connect() as db:
        cur = await db.execute(
            "INSERT INTO groups(name) VALUES(?) ON CONFLICT(name) DO NOTHING",
            (name,),
        )
        await db.commit()
        if cur.lastrowid:
            return cur.lastrowid
        # уже была — вернуть существующий id
        async with db.execute("SELECT id FROM groups WHERE name=?", (name,)) as c2:
            row = await c2.fetchone()
            return row[0] if row else 0


async def list_groups() -> list[Group]:
    async with _connect() as db:
        async with db.execute("SELECT id, name FROM groups ORDER BY name") as cur:
            return [Group(*r) for r in await cur.fetchall()]


async def get_group(group_id: int) -> Optional[Group]:
    async with _connect() as db:
        async with db.execute(
            "SELECT id, name FROM groups WHERE id=?", (group_id,)
        ) as cur:
            row = await cur.fetchone()
            return Group(*row) if row else None


async def delete_group(group_id: int) -> None:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM groups WHERE id=?", (group_id,))
        await db.commit()


# ---------- CATEGORIES ----------

async def create_category(group_id: int, name: str) -> int:
    async with _connect() as db:
        cur = await db.execute(
            "INSERT INTO categories(group_id, name) VALUES(?, ?) "
            "ON CONFLICT(group_id, name) DO NOTHING",
            (group_id, name),
        )
        await db.commit()
        if cur.lastrowid:
            return cur.lastrowid
        async with db.execute(
            "SELECT id FROM categories WHERE group_id=? AND name=?", (group_id, name)
        ) as c2:
            row = await c2.fetchone()
            return row[0] if row else 0


async def list_categories(group_id: int) -> list[Category]:
    """Категории группы с количеством доступных кодов."""
    sql = """
        SELECT c.id, c.group_id, c.name,
               COALESCE(SUM(CASE WHEN k.status='available' THEN 1 ELSE 0 END), 0) AS avail
        FROM categories c
        LEFT JOIN codes k ON k.category_id = c.id
        WHERE c.group_id = ?
        GROUP BY c.id
        ORDER BY c.name
    """
    async with _connect() as db:
        async with db.execute(sql, (group_id,)) as cur:
            return [Category(*r) for r in await cur.fetchall()]


async def get_category(category_id: int) -> Optional[Category]:
    sql = """
        SELECT c.id, c.group_id, c.name,
               COALESCE(SUM(CASE WHEN k.status='available' THEN 1 ELSE 0 END), 0) AS avail
        FROM categories c
        LEFT JOIN codes k ON k.category_id = c.id
        WHERE c.id = ?
        GROUP BY c.id
    """
    async with _connect() as db:
        async with db.execute(sql, (category_id,)) as cur:
            row = await cur.fetchone()
            return Category(*row) if row else None


async def delete_category(category_id: int) -> None:
    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM categories WHERE id=?", (category_id,))
        await db.commit()


async def stock_overview() -> list[tuple[str, str, int]]:
    """Список (group_name, category_name, available_count) только для непустых категорий."""
    sql = """
        SELECT g.name, c.name,
               COALESCE(SUM(CASE WHEN k.status='available' THEN 1 ELSE 0 END), 0) AS avail
        FROM groups g
        JOIN categories c ON c.group_id = g.id
        LEFT JOIN codes k ON k.category_id = c.id
        GROUP BY c.id
        ORDER BY g.name, c.name
    """
    async with _connect() as db:
        async with db.execute(sql) as cur:
            return [(r[0], r[1], r[2]) for r in await cur.fetchall()]


# ---------- CODES ----------

async def add_codes(category_id: int, codes: list[str]) -> tuple[int, int]:
    """Возвращает (added, duplicates). Дубликаты внутри батча тоже считаются."""
    seen: set[str] = set()
    cleaned: list[str] = []
    intra_dups = 0
    for raw in codes:
        c = raw.strip()
        if not c:
            continue
        if c in seen:
            intra_dups += 1
            continue
        seen.add(c)
        cleaned.append(c)

    if not cleaned:
        return 0, intra_dups

    added = 0
    async with _connect() as db:
        for c in cleaned:
            cur = await db.execute(
                "INSERT INTO codes(category_id, code) VALUES(?, ?) "
                "ON CONFLICT(category_id, code) DO NOTHING",
                (category_id, c),
            )
            if cur.rowcount and cur.rowcount > 0:
                added += 1
        await db.commit()

    duplicates = (len(cleaned) - added) + intra_dups
    return added, duplicates


async def take_codes(category_id: int, user_id: int, count: int) -> list[str]:
    """Атомарно берёт до `count` доступных кодов, помечает их и пишет транзакцию.

    Возвращает список выданных кодов (может быть короче запрошенного, если запасов меньше).
    """
    if count <= 0:
        return []

    async with _connect() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT id, code FROM codes "
                "WHERE category_id=? AND status='available' "
                "ORDER BY id LIMIT ?",
                (category_id, count),
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                await db.commit()
                return []

            ids = [r[0] for r in rows]
            codes = [r[1] for r in rows]

            placeholders = ",".join("?" * len(ids))
            await db.execute(
                f"UPDATE codes SET status='taken', taken_by=?, taken_at=CURRENT_TIMESTAMP "
                f"WHERE id IN ({placeholders})",
                (user_id, *ids),
            )
            await db.execute(
                "INSERT INTO transactions(user_id, category_id, count, codes) VALUES(?, ?, ?, ?)",
                (user_id, category_id, len(ids), "\n".join(codes)),
            )
            await db.commit()
            return codes
        except Exception:
            await db.rollback()
            raise


# ---------- HISTORY ----------

async def user_history(user_id: int, limit: int = 30) -> list[TransactionRow]:
    sql = """
        SELECT t.id, g.name, c.name, t.count, t.taken_at, COALESCE(t.codes, '')
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        JOIN groups g ON g.id = c.group_id
        WHERE t.user_id = ?
        ORDER BY t.taken_at DESC
        LIMIT ?
    """
    async with _connect() as db:
        async with db.execute(sql, (user_id, limit)) as cur:
            return [TransactionRow(*r) for r in await cur.fetchall()]


async def get_transaction(tx_id: int, user_id: int) -> Optional[TransactionRow]:
    """Одна транзакция данного пользователя (чтобы не дать читать чужие коды)."""
    sql = """
        SELECT t.id, g.name, c.name, t.count, t.taken_at, COALESCE(t.codes, '')
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        JOIN groups g ON g.id = c.group_id
        WHERE t.id = ? AND t.user_id = ?
    """
    async with _connect() as db:
        async with db.execute(sql, (tx_id, user_id)) as cur:
            row = await cur.fetchone()
            return TransactionRow(*row) if row else None
