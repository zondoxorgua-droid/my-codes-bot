"""Общие команды: /start, /help, /cancel и переход в главное меню."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import keyboards as kb

router = Router(name="common")


HELLO = (
    "<b>Привет!</b>\n\n"
    "Это бот для работы с подарочными кодами.\n"
    "Выбери действие в меню ниже."
)

HELP = (
    "<b>Команды:</b>\n"
    "/start — главное меню\n"
    "/stock — остатки по категориям\n"
    "/history — твоя история выдач\n"
    "/recover — выгрузить ВСЕ выданные тебе коды файлом\n"
    "/cancel — отменить текущее действие\n"
    "/myid — узнать свой Telegram ID"
)


@router.message(CommandStart())
async def on_start(message: Message, state: FSMContext, user_role: str) -> None:
    await state.clear()
    await message.answer(HELLO, reply_markup=kb.main_menu(user_role == "admin"))


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("myid"))
async def on_myid(message: Message) -> None:
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("cancel"))
async def on_cancel(message: Message, state: FSMContext, user_role: str) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=kb.main_menu(user_role == "admin"))


@router.callback_query(F.data == kb.CB_MAIN_ROOT)
async def to_main(call: CallbackQuery, state: FSMContext, user_role: str) -> None:
    await state.clear()
    await call.message.edit_text(HELLO, reply_markup=kb.main_menu(user_role == "admin"))
    await call.answer()


@router.callback_query(F.data == kb.CB_NOOP)
async def noop(call: CallbackQuery) -> None:
    await call.answer()
