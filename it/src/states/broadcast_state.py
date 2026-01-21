from aiogram.fsm.state import StatesGroup, State


class BroadcastState(StatesGroup):
    """
    Состояние в процессе создания сообщения для рассылки пользователям.

    - MessageInput: Ввод сообщения для рассылки
    - WaitingConfirm: Ожидание выбора подтверждения отправки или изменение текста
    - EditMessage: Редактирование сообщения для рассылки
    - ChooseDate: Выбор даты рассылки сообщения
    - ChooseTime: Выбор время рассылки сообщения
    """

    MessageInput = State()
    WaitingConfirm = State()
    EditMessage = State()
    DateSelection = State()
