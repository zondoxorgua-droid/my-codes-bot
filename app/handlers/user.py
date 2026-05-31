"""Пользовательские сценарии: взять коды, посмотреть остатки, историю."""
from __future__ import annotations

import io
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app import db
from app import keyboards as kb
from app.config import MAX_TAKE_PER_REQUEST, TEXT_OUTPUT_THRESHOLD
from app.states import TakeCodes

router = Router(name="user")
log = logging.getLogger("my-codes-bot.issue")


# ============================================================
# Take codes flow: group -> category -> count -> format
# ============================================================

@router.callback_query(F.data == kb.CB_MAIN_TAKE)
async def take_choose_group(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    groups = await db.list_groups()
    if not groups:
        await call.message.edit_text(
            "Пока нет ни одной группы. Попроси админа создать.",
            reply_markup=kb.back_to_main(),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "<b>Шаг 1.</b> Выбери группу карт:",
        reply_markup=kb.groups_kb(groups, cb_prefix=kb.CB_GROUP),
    )
    await call.answer()


@router.callback_query(F.data.startswith(kb.CB_GROUP))
async def take_choose_category(call: CallbackQuery, state: FSMContext) -> None:
    group_id = int(call.data.removeprefix(kb.CB_GROUP))
    group = await db.get_group(group_id)
    if not group:
        await call.answer("Группа не найдена", show_alert=True)
        return
    cats = await db.list_categories(group_id)
    if not cats:
        await call.message.edit_text(
            f"В группе <b>{group.name}</b> ещё нет категорий.",
            reply_markup=kb.back_to_main(),
        )
        await call.answer()
        return
    await call.message.edit_text(
        f"<b>{group.name}</b>\n\n<b>Шаг 2.</b> Выбери номинал (рядом — остаток):",
        reply_markup=kb.categories_kb(cats, cb_prefix=kb.CB_CAT, show_counts=True),
    )
    await call.answer()


@router.callback_query(F.data.startswith(kb.CB_CAT))
async def take_ask_count(call: CallbackQuery, state: FSMContext) -> None:
    category_id = int(call.data.removeprefix(kb.CB_CAT))
    cat = await db.get_category(category_id)
    if not cat:
        await call.answer("Категория не найдена", show_alert=True)
        return
    if cat.available <= 0:
        await call.message.edit_text(
            f"<b>{cat.name}</b>\n\nВ этой категории сейчас нет доступных кодов.",
            reply_markup=kb.back_to_main(),
        )
        await call.answer()
        return

    await state.set_state(TakeCodes.choosing_count)
    await state.update_data(category_id=category_id, available=cat.available, cat_name=cat.name)
    await call.message.edit_text(
        f"<b>{cat.name}</b>\nДоступно: <b>{cat.available}</b>\n\n"
        f"<b>Шаг 3.</b> Сколько кодов выдать? Пришли число (от 1 до {min(cat.available, MAX_TAKE_PER_REQUEST)}).",
        reply_markup=kb.cancel_kb(),
    )
    await call.answer()


@router.message(TakeCodes.choosing_count)
async def take_count_received(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужно прислать число. Попробуй ещё раз или /cancel.")
        return
    n = int(text)
    data = await state.get_data()
    available = int(data.get("available", 0))
    cat_name = data.get("cat_name", "")

    if n <= 0:
        await message.answer("Число должно быть больше нуля.")
        return
    if n > MAX_TAKE_PER_REQUEST:
        await message.answer(f"За один раз можно взять не больше {MAX_TAKE_PER_REQUEST}.")
        return
    if n > available:
        await message.answer(f"Сейчас доступно только {available} шт. Введи число поменьше.")
        return

    await state.update_data(count=n)
    await message.answer(
        f"<b>{cat_name}</b> · <b>{n}</b> шт.\n\n"
        "<b>Шаг 4.</b> Как удобнее получить?",
        reply_markup=kb.output_format_kb(),
    )


@router.callback_query(F.data.in_({kb.CB_FORMAT_TEXT, kb.CB_FORMAT_FILE}), TakeCodes.choosing_count)
async def take_deliver(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    category_id = int(data.get("category_id", 0))
    count = int(data.get("count", 0))
    cat_name = data.get("cat_name", "")
    fmt = "text" if call.data == kb.CB_FORMAT_TEXT else "file"

    codes = await db.take_codes(category_id, call.from_user.id, count)
    await state.clear()

    if not codes:
        await call.message.edit_text(
            "Кто-то успел разобрать коды раньше — сейчас доступно 0. Попробуй другую категорию.",
            reply_markup=kb.back_to_main(),
        )
        await call.answer()
        return

    # Лог выдачи — страховка: коды останутся в journalctl, даже если потеряются в чате
    uname = f"@{call.from_user.username}" if call.from_user.username else "—"
    log.info(
        "ВЫДАЧА | user_id=%s %s | %s | %s шт. | коды: %s",
        call.from_user.id, uname, cat_name, len(codes), ", ".join(codes),
    )

    head = f"<b>{cat_name}</b> — выдано {len(codes)} шт."

    # Авто-выбор формата для слишком больших партий
    if fmt == "text" and len(codes) > TEXT_OUTPUT_THRESHOLD:
        fmt = "file"

    if fmt == "text":
        body = "\n".join(f"<code>{c}</code>" for c in codes)
        await call.message.edit_text(
            f"{head}\n\n{body}",
            reply_markup=kb.back_to_main(),
        )
    else:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch for ch in cat_name if ch.isalnum() or ch in ("-", "_")) or "codes"
        filename = f"{safe_name}_{len(codes)}_{ts}.txt"
        payload = "\n".join(codes).encode("utf-8")
        await call.message.edit_text(head, reply_markup=kb.back_to_main())
        await call.message.answer_document(
            BufferedInputFile(payload, filename=filename),
            caption=f"{cat_name} — {len(codes)} шт.",
        )

    await call.answer("Готово")


# ============================================================
# Stock & history
# ============================================================

@router.callback_query(F.data == kb.CB_MAIN_STOCK)
async def show_stock_cb(call: CallbackQuery) -> None:
    text = await _stock_text()
    await call.message.edit_text(text, reply_markup=kb.back_to_main())
    await call.answer()


@router.message(Command("stock"))
async def show_stock_cmd(message: Message, user_role: str) -> None:
    text = await _stock_text()
    await message.answer(text, reply_markup=kb.main_menu(user_role == "admin"))


async def _stock_text() -> str:
    rows = await db.stock_overview()
    if not rows:
        return "Категорий пока нет."
    lines: list[str] = ["<b>Остатки кодов</b>", ""]
    current_group = ""
    for group_name, cat_name, avail in rows:
        if group_name != current_group:
            if current_group:
                lines.append("")
            lines.append(f"<b>{group_name}</b>")
            current_group = group_name
        marker = "•" if avail > 0 else "·"
        lines.append(f"  {marker} {cat_name}: <b>{avail}</b>")
    return "\n".join(lines)


@router.callback_query(F.data == kb.CB_MAIN_HISTORY)
async def show_history_cb(call: CallbackQuery) -> None:
    rows = await db.user_history(call.from_user.id, limit=15)
    text = _history_text(rows)
    markup = kb.history_kb(rows) if rows else kb.back_to_main()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@router.message(Command("history"))
async def show_history_cmd(message: Message, user_role: str) -> None:
    rows = await db.user_history(message.from_user.id, limit=15)
    text = _history_text(rows)
    markup = kb.history_kb(rows) if rows else kb.main_menu(user_role == "admin")
    await message.answer(text, reply_markup=markup)


def _history_text(rows: list) -> str:
    if not rows:
        return "У тебя ещё нет выдач."
    lines = ["<b>Последние выдачи</b>", "Нажми на любую, чтобы снова получить её коды.", ""]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"<b>{i}.</b> <code>{r.taken_at}</code> · {r.group_name} · "
            f"{r.category_name} · <b>{r.count}</b> шт."
        )
    return "\n".join(lines)


@router.callback_query(F.data.startswith(kb.CB_HIST_ITEM))
async def show_history_codes(call: CallbackQuery) -> None:
    tx_id = int(call.data.removeprefix(kb.CB_HIST_ITEM))
    tx = await db.get_transaction(tx_id, call.from_user.id)
    if not tx:
        await call.answer("Выдача не найдена", show_alert=True)
        return

    codes_list = [c for c in (tx.codes or "").split("\n") if c]
    head = f"<b>{tx.category_name}</b> — {tx.count} шт. · <code>{tx.taken_at}</code>"

    if not codes_list:
        # старые выдачи, сделанные до обновления — коды не сохранялись
        await call.message.answer(
            f"{head}\n\nК сожалению, для этой выдачи коды не сохранены "
            "(она была сделана до обновления бота).",
        )
        await call.answer()
        return

    if len(codes_list) <= TEXT_OUTPUT_THRESHOLD:
        body = "\n".join(f"<code>{c}</code>" for c in codes_list)
        await call.message.answer(f"{head}\n\n{body}")
    else:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch for ch in tx.category_name if ch.isalnum() or ch in ("-", "_")) or "codes"
        filename = f"{safe_name}_{len(codes_list)}_{ts}.txt"
        payload = "\n".join(codes_list).encode("utf-8")
        await call.message.answer_document(
            BufferedInputFile(payload, filename=filename),
            caption=f"{tx.category_name} — {len(codes_list)} шт.",
        )
    await call.answer()
