from aiogram.fsm.state import StatesGroup, State


class TaskStates(StatesGroup):
    """
    Состояния в процессе создания новой заявки.

    Состояния:
    - TextInput: Ввод текста
    - NumberInput: Ввод числа
    - DateInput: Ввод даты
    - FileInput: Файл
    - DateSelection: Выбор даты
    - ListSelection: Выбор элемента из списка
    - CheckboxSelection: Выбор из чекбокса
    - ChoiceSelection: Выбор нескольких элементов из списка
    - OptionalField: Необязательное поле
    - Files: Прикрепление файлов
    - FileUpload: Загрузка файла
    - TaskConfirmation: Подтверждение заявки
    """
    TextInput = State()
    NumberInput = State()
    DateInput = State()
    FileInput = State()
    DateSelection = State()
    ListSelection = State()
    CheckboxSelection = State()
    ChoiceSelection = State()
    OptionalField = State()
    Files = State()
    FileUpload = State()
    TaskConfirmation = State()
