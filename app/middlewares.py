"""Middleware: проверка доступа к боту."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app import db
from app.config import ROOT_ADMIN_ID


class AccessMiddleware(BaseMiddleware):
    """Пропускает только зарегистрированных пользователей и главного админа.

    Главный админ автоматически добавляется при первом обращении.
    Кладёт в data ключ "user_role": 'admin' | 'user'.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Достаём пользователя
        tg_user = None
        if isinstance(event, Update):
            if event.message:
                tg_user = event.message.from_user
            elif event.callback_query:
                tg_user = event.callback_query.from_user

        if tg_user is None:
            return await handler(event, data)

        user_id = tg_user.id
        username = tg_user.username

        # Главный админ — самопровизионинг
        if user_id == ROOT_ADMIN_ID:
            existing = await db.get_user(user_id)
            if existing is None or existing.role != "admin":
                await db.set_user_role(user_id, "admin", username)
            data["user_role"] = "admin"
            return await handler(event, data)

        user = await db.get_user(user_id)
        if user is None:
            # Не пускаем в бота, но даём ответ
            await self._deny(event, user_id)
            return

        # Обновим username, если изменился
        if user.username != username:
            await db.upsert_user(user_id, username)

        data["user_role"] = user.role
        return await handler(event, data)

    @staticmethod
    async def _deny(event: TelegramObject, user_id: int) -> None:
        text = (
            "У тебя нет доступа к этому боту.\n\n"
            f"Твой Telegram ID: <code>{user_id}</code>\n"
            "Передай его админу, чтобы он добавил тебя."
        )
        if isinstance(event, Update):
            if event.message:
                await event.message.answer(text)
            elif event.callback_query:
                await event.callback_query.answer("Доступ запрещён", show_alert=True)
                if event.callback_query.message:
                    await event.callback_query.message.answer(text)
