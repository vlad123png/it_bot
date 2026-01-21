import logging
from typing import Protocol, Type, List

from src.config.ai import STTModel
from src.config.settings import settings
from src.voice_transcription.base_voice_transcription import TranscriptionService
from src.voice_transcription.exceptions import STTError
from .implementation.salute_transcription import SaluteTranscriptionService
from .implementation.whisper_transcription import WhisperTranscriptionService

STT_MAP = {
    STTModel.WHISPER: WhisperTranscriptionService,
    STTModel.SALUTE_SPEECH: SaluteTranscriptionService
}


class TranscriptionOrchestrator(Protocol):
    """
    Интерфейс для оркестратора транскрибации.
    """

    @classmethod
    def initialize_services(cls):
        """
        Инициализирует список доступных сервисов на основе настроек.
        """
        ...

    async def recognize(self, file_path: str) -> str:
        """
        Выполняет транскрибацию аудиофайла, используя выбранные сервисы в определенном порядке.

        :param file_path: Путь к аудио файлу.
        :return: Транскрибированный текст.
        :raises STTError: Если все попытки распознавания завершились неудачей.
        """
        ...


class TranscriptionOrchestratorImpl(TranscriptionOrchestrator):
    """
    Реализация оркестратора для управления процессом транскрибации.
    Пытается выполнить транскрибацию с помощью выбранной модели,
    а при ошибке пробует использовать другие доступные модели.
    """
    _service_order: List[Type[TranscriptionService]] = []  # Список используемых STT моделей.
    _initialized: bool = False  # Флаг инициализации

    @classmethod
    def initialize_services(cls):
        """
        Инициализирует порядок сервисов на основе текущих настроек.
        Первым идет предпочитаемый сервис, затем остальные.
        """
        preferred_model = settings.AI.STT_MODEL
        cls._service_order = [
            STT_MAP[preferred_model],  # Предпочитаемый сервис
            *[service for model, service in STT_MAP.items() if model != preferred_model]  # Остальные сервисы
        ]

    async def recognize(self, file_path: str) -> str:
        if not self._service_order:
            raise RuntimeError(
                'Сервисы не инициализированы. Вызовите TranscriptionOrchestratorImpl.initialize_services().')

        attempted_models = []

        for service_class in self._service_order:
            try:
                logging.debug('Попытка транскрибации с использованием %s', service_class.__name__)
                service_instance = service_class()  # Ленивая инициализация
                return await service_instance.recognize(file_path)
            except (STTError, Exception) as e:
                attempted_models.append(service_class.__name__)
                logging.warning(
                    'Ошибка транскрибации с использованием %s: %s', service_class.__name__, e
                )
                continue

        # Если все попытки неудачны, выбрасываем исключение
        attempted_models_str = ', '.join(attempted_models)
        raise STTError(f'Не удалось выполнить транскрибацию с использованием моделей: {attempted_models_str}')


async def initialize_transcription_orchestrator() -> None:
    """
    Инициализация оркестратора. Нужна для избежания проблем в многопоточной среде.
    Для предварительной загрузки whisper в память, перед началом работы бота.
    Позволяет избежать отложенных проблем. В случае проблем при инициализации мы узнаем об этом до старта бота.
    """
    if not TranscriptionOrchestratorImpl._initialized: # noqa
        TranscriptionOrchestratorImpl.initialize_services()


# Функция для получения оркестратора
async def get_transcription_orchestrator() -> TranscriptionOrchestrator:
    """
    Является фабрикой по сути своей и любое получение модели должно быть только с помощью данной функции.
    Возвращает экземпляр TranscriptionOrchestratorImpl.
    """
    return TranscriptionOrchestratorImpl()
