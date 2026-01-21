import asyncio
import datetime as dt
import json
import logging
import os
import ssl
import uuid

import aiofiles
import aiohttp

from src.config.settings import settings
from src.voice_transcription.base_voice_transcription import TranscriptionService
from src.voice_transcription.exceptions import STTError
from src.voice_transcription.exceptions import STTTimeoutError
from src.voice_transcription.implementation.utils import get_audio_duration


class SaluteTranscriptionService(TranscriptionService):
    """
    Реализация базового класса для работы с транскрибацией аудио в текст по API Salute Speech от Sber.
    - client_secret (str) - ключ для доступа к API.
    - scope (str) - тип доступа к API (персональный или корпоративный).
    - token (str) - токен доступа к API, действует в течении 30 мин.
    - token_expires_at (str) - время жизни токена.
    """

    client_secret: str = settings.AI.SALUTE_SPEECH_CLIENT_SECRET.get_secret_value()
    scope: str = settings.AI.SALUTE_SPEECH_SCOPE.get_secret_value()
    ssl_context: ssl.SSLContext = ssl.create_default_context(
        cafile=settings.AI.SBER_CERTIFICATE_PATH) if settings.AI.SBER_CERTIFICATE_PATH else False

    base_url = 'https://smartspeech.sber.ru/rest/v1/'
    token: str | None = None
    token_expires_at: int | None = None
    max_file_size = 1024  # 1 гигабайт
    max_sync_file_size = 2  # в мегабайтах
    max_sync_file_duration = 60  # в секундах

    async def recognize(self, file_path: str) -> str:
        """
        Транскрибация аудио в текст.

        :param file_path: Путь к аудио файлу.
        :return: Транскрибированный текст.
        :raises FileNotFoundError: Если файл не существует.
        :raises STTError: Если файл слишком большой или длительность превышает лимит.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f'Файл не найден: {file_path}')

        # Получение информации о файле
        try:
            duration = await get_audio_duration(file_path)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        except Exception as e:
            logging.error('Не удалось получить информацию о файле: %s', e)
            raise STTError('Не удалось получить информацию о файле.')

        logging.debug('Размер файла для транскрибации: %.2f МБ. Длительность: %.2f сек.', file_size_mb, duration)

        if file_size_mb > self.max_file_size:
            raise STTError(
                f'Размер аудиофайла ({file_size_mb:.2f} МБ) превышает максимальный допустимый ({self.max_file_size} МБ).')

        # Выбор метода транскрибации
        if file_size_mb < self.max_sync_file_size and duration < self.max_sync_file_duration:
            logging.debug('Используется синхронная транскрибация Sber Speech.')
            return await self._sync_recognize_file(file_path)
        else:
            logging.debug('Используется асинхронная транскрибация Sber Speech.')
            return await self._async_recognize_file(file_path)

    async def _sync_recognize_file(self, file_path: str) -> str:
        """
        Синхронная транскрибация файла.

        :param file_path: Путь к файлу.
        :return: Транскрибированный текст.
        :raises STTError: Если произошла ошибка во время транскрибации.
        """
        url = self.base_url + 'speech:recognize'
        token = await self._get_token()

        headers = {
            'Content-Type': 'audio/ogg;codecs=opus',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        # Чтение файла асинхронно
        try:
            async with aiofiles.open(file_path, 'rb') as audio_file:
                content = await audio_file.read()
        except Exception as e:
            logging.error('Ошибка чтения файла: %s', e)
            raise STTError('Не удалось прочитать файл для синхронной транскрибации.')

        # Отправка POST-запрос
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=content, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    text = ' '.join(data.get('result', ''))
                    logging.debug('Результат синхронной транскрибации: %s', data)
                    return text
                else:
                    response_text = await response.text()
                    logging.error('Ошибка синхронной транскрибации: %s - %s', response.status, response_text)
                    raise STTError(f'Ошибка синхронной транскрибации: {response.status} - {response_text}')

    async def _async_recognize_file(self, file_path: str) -> str:
        """
        Асинхронная транскрибация файла.

        :param file_path: Путь к файлу.
        :return: Транскрибированный текст.
        :raises STTError: Если произошла ошибка во время транскрибации.
        :raises STTTimeoutError: Если транскрибация заняла больше времени, чем разрешено.
        """
        request_file_id = await self.upload_file(file_path)
        task_id = await self.create_recognize_task(request_file_id)

        attempt = 0
        timeout = 300  # в секундах
        sleep_time = 1
        recognized_data = None

        while attempt < timeout:
            result = await self.get_task_status(task_id)
            status = result['status']

            if status == 'DONE':
                recognized_data = await self.download_result(result['response_file_id'])
                break
            elif status in ('ERROR', 'CANCELED'):
                logging.error('Ошибка транскрибации файла: %s', task_id)
                raise STTError(
                    f'Ошибка транскрибации файла {request_file_id}. Статус: {status}'
                )
            elif status in ('NEW', 'RUNNING'):
                await asyncio.sleep(sleep_time)
                attempt += 1
            else:
                logging.error('Неизвестный статус задачи: %s', status)
                raise STTError(f'Неизвестный статус задачи: {status}')


        if not recognized_data:
            raise STTTimeoutError('Превышено время транскрибации!')

        text = '\n'.join(
            [
                result.get('normalized_text') or result.get('text') or ''
                for result in recognized_data[0]['results']
            ]
        )
        logging.debug('Результат транскрибации файла %s: %s', request_file_id, text)
        return text

    async def _get_token(self) -> str:
        """
        Запрашивает или обновляет токен доступа.

        :return: Действительный токен доступа.
        :raises STTError: Если не удалось получить токен.
        """
        if (
                self.token
                and self.token_expires_at
                and dt.datetime.now(dt.UTC).timestamp() * 1000 < self.token_expires_at
        ):
            return self.token

        token_url = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Basic {self.client_secret}'
        }
        payload = {
            'scope': 'SALUTE_SPEECH_CORP'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, headers=headers, data=payload, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get('access_token')
                    self.token_expires_at = data.get('expires_at')
                    logging.debug('Токен доступа Salute Speech успешно получен')
                    return self.token
                else:
                    logging.error('Ошибка получения токена доступа Sber Speech: %s', response.reason)
                    raise STTError(f'Ошибка получения токена Salute Speech: {response.status}')

        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, headers=headers, data=payload, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get('access_token')
                    self.token_expires_at = data.get('expires_at')
                    logging.debug('Токен доступа Salute Speech успешно получен.')
                    return self.token
                else:
                    response_text = await response.text()
                    logging.error('Ошибка получения токена: %s - %s', response.status, response_text)
                    raise STTError(f'Ошибка получения токена: {response.status} - {response_text}')

    async def upload_file(self, file_path: str) -> str:
        """
        Загрузка аудиофайла на сервер Sber Speech.

        :param file_path: Путь к файлу.
        :return: ID загруженного файла.
        :raises STTError: Если произошла ошибка загрузки файла.
        """
        url = self.base_url + 'data:upload'
        token = await self._get_token()

        headers = {
            'Content-Type': 'audio/ogg;codecs=opus',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        try:
            async with aiofiles.open(file_path, 'rb') as audio_file:
                file_content = await audio_file.read()
        except Exception as e:
            logging.error('Ошибка чтения файла: %s', e)
            raise STTError('Не удалось прочитать файл для загрузки.')

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=file_content, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    request_file_id = data['result'].get('request_file_id')
                    logging.debug('ID загруженного файла: %s', request_file_id)
                    return request_file_id
                else:
                    response_text = await response.text()
                    logging.error('Ошибка загрузки файла: %s - %s', response.status, response_text)
                    raise STTError(f'Ошибка загрузки файла: {response.status} - {response_text}')

    async def get_task_status(self, task_id: str):
        """
        Получение статуса задачи транскрибации аудио.

        :param task_id: ID задачи.
        :return: Статус задачи в виде словаря.
        :raises STTError: Если произошла ошибка при получении статуса задачи.
        """
        url = self.base_url + 'task:get'
        token = await self._get_token()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        params = {'id': task_id}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    logging.debug('Статус Salute Speech задачи %s: %s', task_id, data)
                    return data['result']
                else:
                    response_text = await response.text()
                    logging.error(
                        'Ошибка получения статуса задачи Sber Salute Speech для задачи %s: %s - %s',
                        task_id,
                        response.status,
                        response_text,
                    )
                    raise STTError(
                        f'Ошибка получения статуса задачи Sber Salute Speech: {response.status} - {response_text}'
                    )

    async def download_result(self, request_file_id: str) -> list[dict]:
        """
        Загрузка результата транскрибации с сервера Sber Speech.

        :param request_file_id: ID файла результата.
        :return: Список словарей с результатами транскрибации.
        :raises STTError: Если произошла ошибка при загрузке результата.
        """
        url = self.base_url + 'data:download'
        token = await self._get_token()
        params = {'response_file_id': request_file_id}
        headers = {
            'Authorization': f'Bearer {token}'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.read()
                    try:
                        parsed_data = json.loads(data.decode('utf-8'))
                        logging.debug('Загружен файл из Salute Speech %s: %s', request_file_id, parsed_data)
                        return parsed_data
                    except json.JSONDecodeError as e:
                        logging.error('Ошибка декодирования JSON: %s', e)
                        raise STTError(f'Ошибка декодирования JSON результата: {e}')
                else:
                    response_text = await response.text()
                    logging.error(
                        'Ошибка загрузки файла с сервера Sber Salute Speech %s: %s - %s',
                        request_file_id,
                        response.status,
                        response_text,
                    )
                    raise STTError(
                        f'Ошибка загрузки файла с сервера Sber Salute Speech: {response.status} - {response_text}'
                    )

    async def create_recognize_task(self, request_file_id: str):
        """
        Создание задачи транскрибации файла.

        :param request_file_id: ID загруженного файла на сервере Sber Salute Speech.
        :return: ID созданной задачи.
        :raises STTError: Если произошла ошибка при создании задачи.
        """
        url = self.base_url + 'speech:async_recognize'
        token = await self._get_token()
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        payload = {
            'options': {
                'model': 'general',
                'audio_encoding': 'OPUS'
            },
            'request_file_id': request_file_id,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, ssl=self.ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    task_id = data['result'].get('id')
                    logging.debug('Создана задача транскрибации Salute Speech %s: %s', request_file_id, task_id)
                    return task_id
                else:
                    response_text = await response.text()
                    logging.error(
                        'Ошибка создания задачи транскрибации Sber Salute Speech для файла %s: %s - %s',
                        request_file_id,
                        response.status,
                        response_text,
                    )
                    raise STTError(
                        f'Ошибка создания задачи транскрибации Sber Salute Speech: {response.status} - {response_text}'
                    )
