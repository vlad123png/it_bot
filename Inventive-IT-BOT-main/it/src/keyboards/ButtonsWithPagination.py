from aiogram import types, F
from aiogram.exceptions import TelegramBadRequest

from src.config.settings import settings

COUNT_BUTTONS_IN_PAGE = 5


class ButtonsWithPagination:
    """Класс меню с кнопками с пагинацией.

    get_part_menu - функция получения элементов в конкретной итерации
    start - функция запуск меню. Зарегистрироваться в dp.message.register
    update_part_menu - функция обновление меню после нажатия кнопок
    send_menu_back, send_menu_front - реакция кнопок до и после.

    Параметры инициализации:
    dp - Dispatcher. Он тут нужен только для регистрации callback_query.
        Если есть возможность запустить send_... для нажатия кнопки,
        то можно удалить dp.
    menu_buttons - список кнопок меню types.InlineKeyboardButton(...).
    control_buttons - список кнопок для управления меню
        types.InlineKeyboardButton(...).
    text - Надпись в начале меню.
    """
    __number_menu = 0

    @classmethod
    def count_sample(cls):
        cls.__number_menu += 1

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        try:
            cls.COUNT_BUTTONS_IN_PAGE = settings.COUNT_BUTTONS_IN_PAGE
        except AttributeError:
            cls.COUNT_BUTTONS_IN_PAGE = COUNT_BUTTONS_IN_PAGE
        return instance

    def __init__(
        self, dp, menu_buttons=None, control_buttons=None, text='Меню'
    ):
        if menu_buttons is None:
            self.menu_buttons = []
        elif isinstance(menu_buttons, list):
            self.menu_buttons = menu_buttons[:]
        else:
            self.menu_buttons = [menu_buttons]

        if control_buttons is None:
            self.control_buttons = []
        elif isinstance(control_buttons, list):
            self.control_buttons = control_buttons[:]
        else:
            self.control_buttons = [control_buttons]

        self.__first_item = 0
        self.__k_use_items = self.COUNT_BUTTONS_IN_PAGE
        self.text = text
        self.dp = dp
        self.count_sample()
        self.dp.callback_query.register(
            self.send_menu_front,
            F.data == f'menu_front_{self.__number_menu}'
        )
        self.dp.callback_query.register(
            self.send_menu_back,
            F.data == f'menu_back_{self.__number_menu}'
        )

    def get_part_menu(self):
        """Получить элементы.

        Если нужно, добавляются служебные кнопки.
        """
        self.__first_item = max(self.__first_item, 0)
        ib = []
        ib += self.menu_buttons[
            self.__first_item:self.__first_item + self.__k_use_items
        ]

        back_button = [
            types.InlineKeyboardButton(
                text='<<',
                callback_data=f'menu_back_{self.__number_menu}',
            )
        ] if self.__first_item else []

        next_button = [
            types.InlineKeyboardButton(
                text='>>',
                callback_data=f'menu_front_{self.__number_menu}',
            )
        ] if (
            self.__first_item + self.__k_use_items < len(self.menu_buttons)
        ) else []

        if back_button or next_button:
            ib.append(back_button + next_button)

        ib += self.control_buttons

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=ib)
        return keyboard

    async def start(
        self,
        message: types.Message,
        force_new_message: bool = False
    ):
        """Запуск начального меню."""
        if force_new_message:
            await message.answer(
                self.text,
                reply_markup=self.get_part_menu(),
            )
        else:
            try:
                await message.edit_text(
                    self.text,
                    reply_markup=self.get_part_menu(),
                )
            except TelegramBadRequest:
                await message.answer(
                    self.text,
                    reply_markup=self.get_part_menu(),
                )

    async def update_part_menu(self, message: types.Message):
        """Обновление меню."""
        await message.edit_text(
            self.text,
            reply_markup=self.get_part_menu(),
        )

    async def send_menu_back(self, callback: types.CallbackQuery):
        """Нажатие кнопки назад."""
        self.__first_item -= self.__k_use_items
        if self.__first_item <= 1:
            self.__first_item = 0
        await self.update_part_menu(callback.message)

    async def send_menu_front(self, callback: types.CallbackQuery):
        """Нажатие кнопки вперёд."""
        self.__first_item += self.__k_use_items
        await self.update_part_menu(callback.message)
