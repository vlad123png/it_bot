from aiogram.fsm.state import StatesGroup, State


class StatisticState(StatesGroup):
    """
    - select_start_date: Выбор начальной даты сбора статистики
    - select_end_date: Выбор конечной даты сбора статистики
    """
    select_start_date = State()
    select_end_date = State()
