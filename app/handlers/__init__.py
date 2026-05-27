from aiogram import Router

from app.handlers import admin, common, user


def build_root_router() -> Router:
    r = Router(name="root")
    r.include_router(common.router)
    r.include_router(admin.router)
    r.include_router(user.router)
    return r
