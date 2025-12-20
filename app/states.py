from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    number = State()
    location = State()
    work = State()


class SubState(StatesGroup):
    text = State()


class AdminState(StatesGroup):
    login = State()
    password = State()


class SearchDocsStates(StatesGroup):
    waiting_query = State()


class AdminSenderState(StatesGroup):
    text = State()
    photo = State()
    specialization = State()


class AdminAdd(StatesGroup):
    tg_id = State()
    login = State()
    password = State()


class AdminRemove(StatesGroup):
    tg_id = State()


class AdminChange(StatesGroup):
    tg_id = State()
    login = State()
    password = State()