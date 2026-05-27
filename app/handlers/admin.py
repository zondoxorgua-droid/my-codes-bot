"""Админские сценарии: группы, категории, загрузка кодов, пользователи."""
from __future__ import annotations

import io

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Document, Message

from app import db
from app import keyboards as kb
from app.config import ROOT_ADMIN_ID
from app.states import AddCategory, AddGroup, ManageUsers, UploadCodes

router = Router(name="admin")


# Все хендлеры здесь только для админа
async def _is_admin(user_id: int) -> bool:
    if user_id == ROOT_ADMIN_ID:
        return True
    user = await db.get_user(user_id)
    return user is not None and user.role == "admin"


@router.callback_query(F.data == kb.CB_MAIN_ADMIN)
async def open_admin(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text("<b>Админка</b>\nЧто делаем?", reply_markup=kb.admin_menu())
    await call.answer()


# ============================================================
# Add group
# ============================================================

@router.callback_query(F.data == kb.CB_ADM_ADD_GROUP)
async def add_group_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await state.set_state(AddGroup.waiting_for_name)
    await call.message.edit_text(
        "Пришли название новой группы (например, <i>Steam</i> или <i>PSN</i>).",
        reply_markup=kb.cancel_kb(),
    )
    await call.answer()


@router.message(AddGroup.waiting_for_name)
async def add_group_save(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуй ещё или /cancel.")
        return
    if len(name) > 64:
        await message.answer("Слишком длинное название (макс. 64). Попробуй короче.")
        return
    group_id = await db.create_group(name)
    await state.clear()
    await message.answer(
        f"Готово, группа <b>{name}</b> создана (id={group_id}).",
        reply_markup=kb.admin_menu(),
    )


# ============================================================
# Add category
# ============================================================

@router.callback_query(F.data == kb.CB_ADM_ADD_CAT)
async def add_cat_pick_group(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    groups = await db.list_groups()
    if not groups:
        await call.message.edit_text(
            "Сначала создай хотя бы одну группу.",
            reply_markup=kb.admin_menu(),
        )
        await call.answer()
        return
    await state.set_state(AddCategory.waiting_for_name)
    # на этом шаге пользователь ещё не выбрал группу — выбираем через клавиатуру
    await call.message.edit_text(
        "В какую группу добавить категорию?",
        reply_markup=kb.groups_kb(groups, cb_prefix=kb.CB_ADM_PICK_GROUP),
    )
    await call.answer()


@router.callback_query(F.data.startswith(kb.CB_ADM_PICK_GROUP), AddCategory.waiting_for_name)
async def add_cat_group_chosen(call: CallbackQuery, state: FSMContext) -> None:
    group_id = int(call.data.removeprefix(kb.CB_ADM_PICK_GROUP))
    group = await db.get_group(group_id)
    if not group:
        await call.answer("Группа не найдена", show_alert=True)
        return
    await state.update_data(group_id=group_id, group_name=group.name)
    await call.message.edit_text(
        f"Группа: <b>{group.name}</b>\n\nПришли название категории "
        f"(например, <i>500 Robux</i>).",
        reply_markup=kb.cancel_kb(),
    )
    await call.answer()


@router.message(AddCategory.waiting_for_name)
async def add_cat_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    group_id = data.get("group_id")
    if not group_id:
        await message.answer(
            "Сначала выбери группу через кнопки.", reply_markup=kb.admin_menu()
        )
        await state.clear()
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуй ещё или /cancel.")
        return
    if len(name) > 64:
        await message.answer("Слишком длинное название (макс. 64).")
        return
    cat_id = await db.create_category(group_id, name)
    await state.clear()
    await message.answer(
        f"Категория <b>{name}</b> создана (id={cat_id}).",
        reply_markup=kb.admin_menu(),
    )


# ============================================================
# Upload codes
# ============================================================

@router.callback_query(F.data == kb.CB_ADM_UPLOAD)
async def upload_pick_group(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    groups = await db.list_groups()
    if not groups:
        await call.message.edit_text(
            "Нет ни одной группы — нечего наполнять.",
            reply_markup=kb.admin_menu(),
        )
        await call.answer()
        return
    await state.set_state(UploadCodes.waiting_for_payload)
    await call.message.edit_text(
        "В какую группу грузим коды?",
        reply_markup=kb.groups_kb(groups, cb_prefix=kb.CB_ADM_PICK_GROUP),
    )
    await call.answer()


@router.callback_query(F.data.startswith(kb.CB_ADM_PICK_GROUP), UploadCodes.waiting_for_payload)
async def upload_pick_category(call: CallbackQuery, state: FSMContext) -> None:
    group_id = int(call.data.removeprefix(kb.CB_ADM_PICK_GROUP))
    group = await db.get_group(group_id)
    if not group:
        await call.answer("Группа не найдена", show_alert=True)
        return
    cats = await db.list_categories(group_id)
    if not cats:
        await call.message.edit_text(
            f"В группе <b>{group.name}</b> нет категорий. Сначала создай категорию.",
            reply_markup=kb.admin_menu(),
        )
        await state.clear()
        await call.answer()
        return
    await call.message.edit_text(
        f"<b>{group.name}</b>\nВыбери категорию для загрузки:",
        reply_markup=kb.categories_kb(cats, cb_prefix=kb.CB_ADM_PICK_CAT, show_counts=True),
    )
    await call.answer()


@router.callback_query(F.data.startswith(kb.CB_ADM_PICK_CAT), UploadCodes.waiting_for_payload)
async def upload_ready(call: CallbackQuery, state: FSMContext) -> None:
    category_id = int(call.data.removeprefix(kb.CB_ADM_PICK_CAT))
    cat = await db.get_category(category_id)
    if not cat:
        await call.answer("Категория не найдена", show_alert=True)
        return
    await state.update_data(category_id=category_id, cat_name=cat.name)
    await call.message.edit_text(
        f"<b>{cat.name}</b>\n\n"
        "Пришли коды одним из способов:\n"
        "• сообщением — каждый код с новой строки\n"
        "• файлом <code>.txt</code> — каждый код с новой строки\n\n"
        "Дубликаты автоматически отсеются.",
        reply_markup=kb.cancel_kb(),
    )
    await call.answer()


@router.message(UploadCodes.waiting_for_payload, F.document)
async def upload_from_file(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    category_id = data.get("category_id")
    if not category_id:
        await message.answer("Сначала выбери категорию через кнопки.")
        return

    doc: Document = message.document
    if doc.file_size and doc.file_size > 5 * 1024 * 1024:
        await message.answer("Файл слишком большой (>5 МБ). Раздели на части.")
        return

    buf = io.BytesIO()
    await bot.download(doc, destination=buf)
    raw = buf.getvalue().decode("utf-8", errors="replace")
    lines = raw.splitlines()

    added, dups = await db.add_codes(int(category_id), lines)
    cat = await db.get_category(int(category_id))
    await state.clear()
    await message.answer(
        f"Загружено в <b>{cat.name if cat else '?'}</b>:\n"
        f"• Добавлено: <b>{added}</b>\n"
        f"• Дубликатов/пустых пропущено: {dups}\n"
        f"• Всего доступно сейчас: <b>{cat.available if cat else '?'}</b>",
        reply_markup=kb.admin_menu(),
    )


@router.message(UploadCodes.waiting_for_payload, F.text)
async def upload_from_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    category_id = data.get("category_id")
    if not category_id:
        await message.answer("Сначала выбери категорию через кнопки.")
        return

    lines = (message.text or "").splitlines()
    added, dups = await db.add_codes(int(category_id), lines)
    cat = await db.get_category(int(category_id))
    await state.clear()
    await message.answer(
        f"Загружено в <b>{cat.name if cat else '?'}</b>:\n"
        f"• Добавлено: <b>{added}</b>\n"
        f"• Дубликатов/пустых пропущено: {dups}\n"
        f"• Всего доступно сейчас: <b>{cat.available if cat else '?'}</b>",
        reply_markup=kb.admin_menu(),
    )


# ============================================================
# Delete group / category (с подтверждением)
# ============================================================

@router.callback_query(F.data == kb.CB_ADM_DEL_GROUP)
async def del_group_pick(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    groups = await db.list_groups()
    if not groups:
        await call.message.edit_text("Групп нет.", reply_markup=kb.admin_menu())
        await call.answer()
        return
    await call.message.edit_text(
        "Какую группу удалить? <b>Все её категории и коды будут удалены</b>.",
        reply_markup=kb.groups_kb(groups, cb_prefix=kb.CB_CONFIRM_DEL_GROUP),
    )
    await call.answer()


@router.callback_query(F.data.startswith(kb.CB_CONFIRM_DEL_GROUP))
async def del_group_confirm(call: CallbackQuery) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    group_id = int(call.data.removeprefix(kb.CB_CONFIRM_DEL_GROUP))
    group = await db.get_group(group_id)
    if not group:
        await call.answer("Уже удалена", show_alert=True)
        return
    await db.delete_group(group_id)
    await call.message.edit_text(
        f"Группа <b>{group.name}</b> удалена.", reply_markup=kb.admin_menu()
    )
    await call.answer()


@router.callback_query(F.data == kb.CB_ADM_DEL_CAT)
async def del_cat_pick_group(call: CallbackQuery) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    groups = await db.list_groups()
    if not groups:
        await call.message.edit_text("Групп нет.", reply_markup=kb.admin_menu())
        await call.answer()
        return
    await call.message.edit_text(
        "Из какой группы удалить категорию?",
        # Используем спец-префикс, чтобы не пересечься с upload-flow (там нужно состояние)
        reply_markup=kb.groups_kb(groups, cb_prefix="delgrp_pick:"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delgrp_pick:"))
async def del_cat_pick_cat(call: CallbackQuery) -> None:
    group_id = int(call.data.removeprefix("delgrp_pick:"))
    group = await db.get_group(group_id)
    if not group:
        await call.answer("Группа не найдена", show_alert=True)
        return
    cats = await db.list_categories(group_id)
    if not cats:
        await call.message.edit_text(
            f"В группе <b>{group.name}</b> нет категорий.", reply_markup=kb.admin_menu()
        )
        await call.answer()
        return
    await call.message.edit_text(
        f"<b>{group.name}</b>\nКакую категорию удалить? "
        f"<b>Коды этой категории тоже будут удалены</b>.",
        reply_markup=kb.categories_kb(cats, cb_prefix=kb.CB_CONFIRM_DEL_CAT, show_counts=True),
    )
    await call.answer()


@router.callback_query(F.data.startswith(kb.CB_CONFIRM_DEL_CAT))
async def del_cat_confirm(call: CallbackQuery) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    cat_id = int(call.data.removeprefix(kb.CB_CONFIRM_DEL_CAT))
    cat = await db.get_category(cat_id)
    if not cat:
        await call.answer("Уже удалена", show_alert=True)
        return
    await db.delete_category(cat_id)
    await call.message.edit_text(
        f"Категория <b>{cat.name}</b> удалена.", reply_markup=kb.admin_menu()
    )
    await call.answer()


# ============================================================
# Users management
# ============================================================

@router.callback_query(F.data == kb.CB_ADM_USERS)
async def users_open(call: CallbackQuery) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    users = await db.list_users()
    lines = ["<b>Пользователи бота</b>", ""]
    if not users:
        lines.append("Никого нет.")
    else:
        for u in users:
            tag = f"@{u.username}" if u.username else "—"
            lines.append(f"<code>{u.user_id}</code> · {tag} · <b>{u.role}</b>")
    await call.message.edit_text("\n".join(lines), reply_markup=kb.users_menu())
    await call.answer()


@router.callback_query(F.data == kb.CB_USER_ADD)
async def user_add_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await state.set_state(ManageUsers.waiting_for_user_id)
    await state.update_data(action="add")
    await call.message.edit_text(
        "Пришли Telegram ID пользователя, которого надо <b>добавить</b>.\n"
        "ID можно получить через @userinfobot.",
        reply_markup=kb.cancel_kb(),
    )
    await call.answer()


@router.callback_query(F.data == kb.CB_USER_REMOVE)
async def user_remove_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_admin(call.from_user.id):
        await call.answer("Только для админа", show_alert=True)
        return
    await state.set_state(ManageUsers.waiting_for_user_id)
    await state.update_data(action="remove")
    await call.message.edit_text(
        "Пришли Telegram ID пользователя, которого надо <b>удалить</b>.",
        reply_markup=kb.cancel_kb(),
    )
    await call.answer()


@router.message(ManageUsers.waiting_for_user_id)
async def user_id_received(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("Нужен числовой ID. Попробуй ещё раз или /cancel.")
        return
    target_id = int(text)
    data = await state.get_data()
    action = data.get("action", "add")
    await state.clear()

    if target_id == ROOT_ADMIN_ID:
        await message.answer(
            "Этого пользователя нельзя менять — он главный админ.",
            reply_markup=kb.admin_menu(),
        )
        return

    if action == "add":
        await db.set_user_role(target_id, "user")
        await message.answer(
            f"Пользователь <code>{target_id}</code> добавлен.",
            reply_markup=kb.admin_menu(),
        )
    else:
        await db.delete_user(target_id)
        await message.answer(
            f"Пользователь <code>{target_id}</code> удалён.",
            reply_markup=kb.admin_menu(),
        )
