"""Inline-клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db import Category, Group


# ---------- callback data prefixes ----------
# Делаем простыми строками вместо CallbackData-фабрик для прозрачности.

CB_MAIN_TAKE = "main:take"
CB_MAIN_STOCK = "main:stock"
CB_MAIN_HISTORY = "main:history"
CB_MAIN_ADMIN = "main:admin"
CB_MAIN_ROOT = "main:root"  # вернуться в главное меню

# take flow
CB_GROUP = "grp:"            # grp:<id>
CB_CAT = "cat:"              # cat:<id>
CB_FORMAT_TEXT = "fmt:text"
CB_FORMAT_FILE = "fmt:file"

# admin
CB_ADM_ADD_GROUP = "adm:addgrp"
CB_ADM_ADD_CAT = "adm:addcat"
CB_ADM_UPLOAD = "adm:upload"
CB_ADM_USERS = "adm:users"
CB_ADM_DEL_GROUP = "adm:delgrp"
CB_ADM_DEL_CAT = "adm:delcat"

CB_ADM_PICK_GROUP = "admgrp:"   # admgrp:<id> — выбор группы для сценария
CB_ADM_PICK_CAT = "admcat:"     # admcat:<id> — выбор категории для сценария

CB_USER_ADD = "usr:add"
CB_USER_REMOVE = "usr:rm"

CB_CONFIRM_DEL_GROUP = "delgrp:"  # delgrp:<id>
CB_CONFIRM_DEL_CAT = "delcat:"    # delcat:<id>

# history
CB_HIST_ITEM = "hist:"            # hist:<tx_id> — показать коды выдачи заново

CB_NOOP = "noop"


def main_menu(is_admin: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Взять коды", callback_data=CB_MAIN_TAKE)
    b.button(text="Остатки", callback_data=CB_MAIN_STOCK)
    b.button(text="История", callback_data=CB_MAIN_HISTORY)
    if is_admin:
        b.button(text="Админка", callback_data=CB_MAIN_ADMIN)
    b.adjust(1, 2, 1) if is_admin else b.adjust(1, 2)
    return b.as_markup()


def back_to_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="В меню", callback_data=CB_MAIN_ROOT)
    return b.as_markup()


def groups_kb(groups: list[Group], cb_prefix: str = CB_GROUP) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in groups:
        b.button(text=g.name, callback_data=f"{cb_prefix}{g.id}")
    if not groups:
        b.button(text="(пусто)", callback_data=CB_NOOP)
    b.button(text="« В меню", callback_data=CB_MAIN_ROOT)
    b.adjust(2)
    return b.as_markup()


def categories_kb(
    categories: list[Category],
    cb_prefix: str = CB_CAT,
    show_counts: bool = True,
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        label = f"{c.name} · {c.available}" if show_counts else c.name
        b.button(text=label, callback_data=f"{cb_prefix}{c.id}")
    if not categories:
        b.button(text="(пусто)", callback_data=CB_NOOP)
    b.button(text="« В меню", callback_data=CB_MAIN_ROOT)
    b.adjust(2)
    return b.as_markup()


def output_format_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Текстом", callback_data=CB_FORMAT_TEXT)
    b.button(text="Файлом .txt", callback_data=CB_FORMAT_FILE)
    b.button(text="« Отмена", callback_data=CB_MAIN_ROOT)
    b.adjust(2, 1)
    return b.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="+ Группа", callback_data=CB_ADM_ADD_GROUP)
    b.button(text="+ Категория", callback_data=CB_ADM_ADD_CAT)
    b.button(text="Загрузить коды", callback_data=CB_ADM_UPLOAD)
    b.button(text="Пользователи", callback_data=CB_ADM_USERS)
    b.button(text="Удалить группу", callback_data=CB_ADM_DEL_GROUP)
    b.button(text="Удалить категорию", callback_data=CB_ADM_DEL_CAT)
    b.button(text="« В меню", callback_data=CB_MAIN_ROOT)
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def users_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Добавить пользователя", callback_data=CB_USER_ADD)
    b.button(text="Удалить пользователя", callback_data=CB_USER_REMOVE)
    b.button(text="« Назад", callback_data=CB_MAIN_ADMIN)
    b.adjust(1)
    return b.as_markup()


def confirm_kb(yes_data: str, no_data: str = CB_MAIN_ADMIN) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Да, удалить", callback_data=yes_data)
    b.button(text="Отмена", callback_data=no_data)
    b.adjust(2)
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Отмена", callback_data=CB_MAIN_ROOT)
    return b.as_markup()


def history_kb(rows: list) -> InlineKeyboardMarkup:
    """Кнопка на каждую выдачу — повторно показать её коды.

    rows: список TransactionRow (берём .id, .category_name, .count).
    """
    b = InlineKeyboardBuilder()
    for i, r in enumerate(rows, start=1):
        b.button(
            text=f"{i}. {r.category_name} · {r.count} шт.",
            callback_data=f"{CB_HIST_ITEM}{r.id}",
        )
    b.button(text="« В меню", callback_data=CB_MAIN_ROOT)
    b.adjust(1)
    return b.as_markup()
