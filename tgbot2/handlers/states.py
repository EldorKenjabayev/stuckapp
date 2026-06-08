from aiogram.fsm.state import StatesGroup, State


class Form(StatesGroup):
    name = State()
    specialization = State()
    specialist_dict = State()

class Query(StatesGroup):
    name = State()
    desc = State()
