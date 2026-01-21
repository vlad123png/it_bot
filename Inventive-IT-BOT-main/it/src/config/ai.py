from enum import StrEnum

from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings


class STTModel(StrEnum):
    """
    Модели Text to Speach с которыми работает бот.
    Для добавления новой модели так же нужно написать реализацию базового класса и добавить в фабрику.
    """
    WHISPER = 'whisper'
    SALUTE_SPEECH = 'salute_speech'


class AISettings(BaseSettings):
    """
    Настройки ИИ.

    Найстройки:
    - REQUESTS_COUNT: (int): Количество обращений к ИИ в сутки
    - STT_MODEL (TTSModel): Модель транскрибации аудио
    """
    # Sber (GigaChat) credentials
    REQUESTS_COUNT: int = Field(ge=0)
    STT_MODEL: STTModel

    SBER_CERTIFICATE_PATH: str | None = None
    SALUTE_SPEECH_SCOPE: SecretStr
    SALUTE_SPEECH_CLIENT_SECRET: SecretStr

    class Config:
        env_file = '.env'
        extra = 'ignore'
        validate_assignment = True
