"""FSM-состояния."""
from aiogram.fsm.state import State, StatesGroup


class TakeCodes(StatesGroup):
    """Пользователь берёт коды."""
    choosing_count = State()    # ввёл количество


class AddGroup(StatesGroup):
    waiting_for_name = State()


class AddCategory(StatesGroup):
    waiting_for_name = State()  # group_id хранится в data


class UploadCodes(StatesGroup):
    waiting_for_payload = State()  # category_id хранится в data


class ManageUsers(StatesGroup):
    waiting_for_user_id = State()  # action ('add'|'remove') хранится в data
