import locale
from datetime import datetime

from aiogram.types import User

from .schemas import CalendarLabels


async def get_user_locale(from_user: User) -> str:
    """Returns user locale in format en_US, accepts User instance from Message, CallbackData etc"""
    loc = from_user.language_code
    return locale.locale_alias[loc].split(".")[0]


class GenericCalendar:

    def __init__(
        self,
        locale: str = None,
        cancel_btn: str = None,
        today_btn: str = None,
        show_alerts: bool = False
    ) -> None:
        """Pass labels if you need to have alternative language of buttons

        Parameters:
        locale (str): Locale calendar must have captions in (in format uk_UA), if None - default English will be used
        cancel_btn (str): label for button Cancel to cancel date input
        today_btn (str): label for button Today to set calendar back to todays date
        show_alerts (bool): defines how the date range error would shown (defaults to False)
        """
        self._labels = CalendarLabels()

        self._labels.days_of_week = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        self._labels.months = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

        self._labels.cancel_caption = 'Отмена'
        self._labels.today_caption = 'Сегодня'

        self.min_date: datetime | None = None
        self.max_date: datetime | None = None
        self.show_alerts = show_alerts

    def set_dates_range(self, min_date: datetime | None, max_date: datetime | None):
        """Sets range of minimum & maximum dates"""
        self.min_date = min_date.date() if min_date else None
        self.max_date = max_date.date() if max_date else None

    async def process_day_select(self, data, query):
        """Checks selected date is in allowed range of dates"""
        date = datetime(int(data.year), int(data.month), int(data.day))
        if self.min_date and self.min_date > date.date():
            await query.answer(
                f'Дата должна быть позже {self.min_date.strftime("%d.%m.%Y")}',
                show_alert=self.show_alerts
            )
            return False, None
        elif self.max_date and self.max_date < date.date():
            await query.answer(
                f'Дата должна быть раньше {self.max_date.strftime("%d.%m.%Y")}',
                show_alert=self.show_alerts
            )
            return False, None
        await query.message.delete_reply_markup()  # removing inline keyboard
        return True, date
