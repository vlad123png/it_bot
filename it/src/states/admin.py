from aiogram.fsm.state import StatesGroup, State


class AdminState(StatesGroup):
    """
    Состояние в процеесе работы с административной панелью.

    Состояния:
    - AddAdminEmailInput: Ввод адреса электронной почты для предоставления прав администратора
    - RemoveAdminEmailInput: Ввод адреса электронной почты для удаления прав администратора
    - NewSettingInput: Ввод нового параметра конфигурации бота
    - ConfirmNewParameter: Подтверждения изменение настройки бота
    - WaitingSurveyId: Ожидание ввода идентификатора опроса для получения результата
    - WaitingGoogleSheetURLInput: Ожидание ввода URL гугл таблицы для тестирования
    - WaitingSheetNameInput: Ожидание ввода имени листа в таблице для тестирования
    """
    EmailInput = State()
    NewSettingInput = State()
    MessageFromBroadcastInput = State()
    WaitingSurveyId = State()

    # TESTING
    WaitingGoogleSheetURLInput = State()
    WaitingSheetNameInput = State()
