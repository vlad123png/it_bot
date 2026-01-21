import datetime
import os
from datetime import timedelta

from dotenv import load_dotenv
from pydantic import SecretStr, HttpUrl, Field
from pydantic_settings import BaseSettings

from .ai import AISettings
from .backend_api import BackendAPISettings
from .mysql import DBSettings
from .redis import RedisSettings


class Settings(BaseSettings):
    """
    Настройки бота.

    Настройки:
    - DEBUG (bool): Тестовый режим бота
    - MYSQL (MySQLSettings): Объект настройки базы данных
    - REDIS (RedisSettings): Объект настройки БД redis
    - AI (AISettings): Объект Настройки ИИ

    - TG_TOKEN (SecretStr): Токен для работы с Telegram API
    - BOT_VERSION (str): Версия бота
    - MODEL_WHISPER(str): модель для транскрибации

    - API_URL (HttpUrl): URL Inventive API
    - API_LOGIN (str): Логин пользователя в Inventive API
    - API_PASSWORD (SecretStr): Пароль пользователя в Inventive API

  Используется как заглушка, но должен совпадать с указанным в настройках интеграции.

    - SMTP_HOST (str): Хост SMTP-сервера
    - SMTP_PORT (str): Порт SMTP-сервера
    - USE_SSL (bool): Использовать SSL для соединения
    - HOST_USERNAME (str): Имя пользователя
    - HOST_PASSWORD (SecretStr): Пароль пользователя
    - SENDER_EMAIL (str): E-mail отправителя

    - WORK_HOURS_START(int): Время начала рабочего дня
    - WORK_HOURS_END(int): Время окончания рабочего дня
    - BROADCAST_TIME (time): Время рассылки сообщений
    - SLEEP_TIME(int): Время в секундах перед удалением сообщений
    - CACHE_TIMEOUT (timedelta): Время жизни кэша
    - QR_CODE_ENCODED (bool): QR код закодирован в Base64
    - ASK_OPTIONAL_FIELDS (bool): Спрашивать необязательные поля заявки
    - ANTIFLOOD_TIMEOUT (int): Время анти-флуд (в секундах)
    - AUTH_DURATION (timedelta): Время действия аутентификации
    - AUTH_ATTEMPTS (int): Лимит попыток ввода кода подтверждения
    - VERIFICATION_CODE_DURATION (timedelta): Время действия кода подтверждения
    - COUNT_BUTTONS_IN_PAGE (int): Количество отображаемых кнопок
    - MAX_FILE_SIZE_MB (int): Максимальный размер загружаемого файла в мегабайтах
    - MAX_TOTAL_UPLOAD_SIZE_MB (int): Максимальный размер файлов прикрепляемых к заявке
    - TEMP_FILES_DIR (str): Директория для хранения временных файлов
    - LOG_DIR (str): Директория для хранения лог-файлов
    - APP_LOG_FILE_NAME (str): Лог-файл событий и ошибок
    - USER_ACTIVITY_LOG_FILE_NAME (str): Лог-файл действий пользователей
    - LOGGING_CONFIG (dict): Настройки логирования

    - Config: Внутренний класс Pydantic для импорта настроек из .env
    """
    DEBUG: bool = False

    DB: DBSettings = Field(default_factory=DBSettings)
    AI: AISettings = Field(default_factory=AISettings)
    REDIS: RedisSettings = Field(default_factory=RedisSettings)
    BACKEND_API: BackendAPISettings = Field(default_factory=BackendAPISettings)

    TG_TOKEN: SecretStr
    BOT_VERSION: str
    MODEL_WHISPER: str

    API_URL: HttpUrl
    API_LOGIN: str
    API_PASSWORD: SecretStr

    SMTP_HOST: str
    SMTP_PORT: int
    USE_SSL: bool
    HOST_USERNAME: str
    HOST_PASSWORD: SecretStr
    SENDER_EMAIL: str
    HELP_EMAIL: str
    FEEDBACK_EMAIL: str
    ERROR_EMAIL: str

    WORK_HOURS_START: int = 8
    WORK_HOURS_END: int = 17
    USER_AGREEMENT_CACHE_TIME: int = 60 * 60 * 24
    BROADCAST_TIME: datetime.time = datetime.time(10, 00)
    MAX_MESSAGE_LENGTH: int = 4000
    SLEEP_TIME: int = Field(default=10, gt=0)
    CACHE_TIMEOUT: timedelta = timedelta(hours=1)
    QR_CODE_ENCODED: bool = True
    ASK_OPTIONAL_FIELDS: bool = False
    ANTIFLOOD_TIMEOUT: int = Field(default=2, gt=0)
    AUTH_DURATION: timedelta = timedelta(days=30)
    AUTH_ATTEMPTS: int = Field(default=3, gt=0)
    VERIFICATION_CODE_DURATION: timedelta = timedelta(minutes=5)
    COUNT_BUTTONS_IN_PAGE: int = Field(default=10, gt=5)
    MAX_FILE_SIZE_MB: int = Field(default=5, gt=0)
    MAX_TOTAL_UPLOAD_SIZE_MB: int = Field(default=25, gt=0)
    TEMP_FILES_DIR: str = 'temp'
    LOG_DIR: str = 'logs'
    APP_LOG_FILE_NAME: str = 'app.log'
    USER_ACTIVITY_LOG_FILE_NAME: str = 'user_activity.log'

    @property
    def LOGGING_CONFIG(self) -> dict:
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'app_file': {
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': os.path.join(self.LOG_DIR, self.APP_LOG_FILE_NAME),
                    'when': 'W0',
                    'backupCount': 4,
                    'encoding': 'utf-8',
                    'level': 'DEBUG' if self.DEBUG else 'INFO',
                    'formatter': 'standard',
                },
                'user_activity_file': {
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': os.path.join(self.LOG_DIR, self.USER_ACTIVITY_LOG_FILE_NAME),
                    'when': 'midnight',
                    'interval': 1,
                    'backupCount': 30,
                    'encoding': 'utf-8',
                    'level': 'DEBUG' if self.DEBUG else 'INFO',
                    'formatter': 'standard',
                },
            },
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(message)s',
                },
            },
            'loggers': {
                '': {
                    'handlers': ['app_file'],
                    'level': 'DEBUG' if self.DEBUG else 'INFO',
                    'propagate': True,
                },
                'user_activity': {
                    'handlers': ['user_activity_file'],
                    'level': 'DEBUG' if self.DEBUG else 'INFO',
                    'propagate': False,
                },
            },
        }

    class Config:
        env_file = '.env'
        extra = 'ignore'
        validate_assignment = True


def load_settings():
    """
    Загружает настройки из переменных окружения.
    """
    load_dotenv()
    return Settings()  # noqa


settings = load_settings()
