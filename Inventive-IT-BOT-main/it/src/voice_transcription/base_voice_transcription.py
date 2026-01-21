from typing import Protocol


class TranscriptionService(Protocol):

    async def recognize(self, file_path: str) -> str:
        """
        Транскрибация аудио в текст
        :param file_path: Путь к аудио файлу
        """
        ...
