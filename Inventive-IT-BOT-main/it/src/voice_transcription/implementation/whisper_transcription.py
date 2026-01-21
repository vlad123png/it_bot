import asyncio
import logging

import whisper
from whisper import Whisper

from src.config.settings import settings
from src.voice_transcription.base_voice_transcription import TranscriptionService
from src.voice_transcription.exceptions import STTError


class WhisperTranscriptionService(TranscriptionService):
    """ Реализация базового класса для работы с транскрибацией аудио в текст с помощью модели whisper. """
    model = None

    @classmethod
    def _get_model(cls) -> Whisper:
        if not cls.model:
            cls.model = whisper.load_model(settings.MODEL_WHISPER)
        return cls.model

    async def recognize(self, file_path: str) -> str:
        """
        Транскрибация аудио в текст
        :param file_path: Путь к аудио файлу
        """
        try:
            system_whisper_prompt = settings.AI.WHISPER_PROMPT
            stt = self._get_model()
            # Запуск транскрибации в пуле потоков
            result = await asyncio.to_thread(
                lambda: stt(file_path, fp16=False, prompt=system_whisper_prompt)
            )
            logging.debug('Whisper трансгрибация: %s', str(result['text']))
            return str(result['text'])

        except Exception as e:
            raise STTError(f'Ошибка трансгрибации файла whisper {e}')
