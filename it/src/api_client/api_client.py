import json
import logging
from datetime import datetime, timedelta
from json import JSONDecodeError
from pathlib import Path
from typing import List, Tuple, Literal

from aiohttp import ClientSession, BasicAuth, FormData, client_exceptions

from src.config.settings import settings
from .exceptions import APIError, ClientError, APIPermissionError
from .utils import get_content_type, clean_none_values

PAGE_SIZE: int = 1000
ROOT_ARED_SERVICE_IDS = ["763"]
ALLOW_FOR_ARED_IDS = []
EXCLUDE_SERVICES_IDS = ["761", "792", "804", "805", "808", "809", "810", "811", "813", "850", "1062", "1063", "1064",
                        "1065", "1123", "1126", "1196", "1198", "1207", "1224", ]


class APIClient:
    """
    Клиент для взаимодействия с API.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(APIClient, cls).__new__(cls)
            cls._instance._initialize(*args, **kwargs)
        return cls._instance

    def _initialize(
            self,
            login,
            password,
            url,
            cache_timeout=timedelta(hours=1)
    ):
        """
            :param login: Логин пользователя
            :type login: str
            :param password: Пароль пользователя
            :type password: str
            :param url: URL API
            :type url: str
            :param cache_timeout: Время жизни кэша
            :type cache_timeout: timedelta, optional
        """
        self.auth = BasicAuth(login, password)
        self.url = url
        self.cache_timeout = cache_timeout
        self.cache = {}
        self.session = None

    async def __aenter__(self):
        if not self.session or self.session.closed:
            self.session = ClientSession(auth=self.auth)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Не закрываем сессию автоматически, так как это синглтон."""
        pass

    async def close(self):
        """Метод для явного закрытия сессии при завершении работы приложения."""
        if self.session and not self.session.closed:
            await self.session.close()

    def _cache_has_expired(self, key):
        if key in self.cache:
            timestamp = self.cache[key]['timestamp']
            return datetime.utcnow() - timestamp > self.cache_timeout
        return True

    async def _handle_response(self, response):
        if 200 <= response.status < 400:
            return await response.json()
        if 400 <= response.status < 600:
            text = await response.text()
            if 'у пользователя нет прав создавать заявки на этом сервисе' in text.lower():
                raise APIPermissionError('У пользователя нет прав создавать заявки на этом сервисе')

            try:
                err = json.loads(text)
            except JSONDecodeError:
                raise ClientError(response.status, text)
            raise ClientError(
                response.status,
                err.get('Message'),
                err.get('MessageDetail')
            )
        raise ClientError(response.status, 'Неожиданный код ответа API.')

    def _log_request(self, method, url):
        logging.debug(f'{method}: {url}')

    async def _send_request(
            self,
            method,
            endpoint,
            params=None,
            data=None,
            json=None,
            headers=None
    ):
        url = f'{self.url}/{endpoint}'
        self._log_request(method, url)
        try:
            async with self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json,
                    headers=headers
            ) as response:
                return await self._handle_response(response)
        except client_exceptions.ClientConnectorError as e:
            raise APIError(
                f'Url:{endpoint} Headers: {headers} Params: {params} Json: {json} Data: {data} Ошибка: {str(e)}')

    async def _get_all(self, endpoint, key, params=None):
        params = params or {}
        params.update({'pagesize': PAGE_SIZE, 'page': 1})
        items = []
        while True:
            data = await self._send_request(
                'GET',
                endpoint,
                params=params
            )
            items.extend(data[key])
            if data['Paginator']['Page'] == data['Paginator']['PageCount']:
                return items
            params['page'] += 1

    async def get_user(self, id: int) -> dict:
        """
        Получает пользователя по его идентификатору.

        :param id: Идентификатор пользователя
        :type id: int

        :return: Пользователь
        :rtype: dict
        """
        key = f'user_{id}'
        if key in self.cache and not self._cache_has_expired(key):
            return self.cache[key]['data']
        user = await self._fetch_user(id)
        self.cache[key] = {
            'data': user, 'timestamp': datetime.utcnow()
        }
        return user

    async def _fetch_user(self, id: int) -> dict:
        return await self._send_request('GET', f'user/{id}')

    async def get_users(self, email: str = None) -> List[dict]:
        """
        Получает список пользователей.

        :param email: Адрес электронной почты для фильтрации пользователей
        :type email: str, optional

        :return: Список пользователей
        :rtype: List[dict]
        """
        params = {}
        if email:
            params['email'] = email
        users = await self._get_all('user', 'Users', params=params)
        return users

    async def _fetch_services(self) -> List[dict]:
        services = await self._get_all(
            'service',
            'Services',
            params={'for': 'createtask'}
        )
        return services

    async def get_services(self, service_group: Literal['all', 'main', 'ared']) -> List[dict]:
        """
        Получает список сервисов.

        :param service_group: Группа сервисов
        :return: Список сервисов
        :rtype: List[dict]
        """
        if 'services' not in self.cache or self._cache_has_expired('services'):
            services = await self._fetch_services()
            self.cache['services'] = {
                'data': services, 'timestamp': datetime.utcnow()
            }
        services = self.cache['services']['data']

        if service_group == 'main':
            main_services = [
                service for service in services if
                not any(
                    service['Path'].startswith(ared_id) for ared_id in ROOT_ARED_SERVICE_IDS + EXCLUDE_SERVICES_IDS)]
            return main_services

        elif service_group == 'ared':
            if 'ared_services' not in self.cache or self._cache_has_expired('ared_services'):
                parse_path = lambda path_str: [part.strip() for part in path_str.split('|') if part]
                allow_services = [service for service in services if
                                  any(allow_id in service['Path'] for allow_id in ALLOW_FOR_ARED_IDS)]
                allow_services_ids = set()
                for allow_service in allow_services:
                    ids = [allow_id for allow_id in parse_path(allow_service['Path']) if allow_id]
                    allow_services_ids.update(ids)

                ared_services = []
                for service in services:
                    path = parse_path(service['Path'])
                    if not any(exlude_id in path for exlude_id in EXCLUDE_SERVICES_IDS):
                        if any(allow_root_id in path for allow_root_id in ROOT_ARED_SERVICE_IDS):
                            ared_services.append(service)

                        elif any(path[-1] == allow_id for allow_id in allow_services_ids):
                            ared_services.append(service)
                            allow_services_ids.remove(path[-1])

                self.cache['ared_services'] = {
                    'data': ared_services, 'timestamp': datetime.utcnow()
                }
            ared_services = self.cache['ared_services']['data']
            return ared_services

        return services

    async def get_assets(self, service_id: int) -> List[dict]:
        """
        Получает список активов для указанного сервиса.

        :param service_id: Идентификатор сервиса
        :type service_id: int

        :return: Список активов
        :rtype: List[dict]
        """
        assets = await self._get_all(
            'asset',
            'Assets',
            params={'serviceid': service_id}
        )
        return assets

    async def get_categories(self, service_id: int) -> List[dict]:
        """
        Получает список категорий для указанного сервиса.

        :param service_id: Идентификатор сервиса
        :type service_id: int

        :return: Список категорий
        :rtype: List[dict]
        """
        categories = await self._get_all(
            'category',
            'Categories',
            params={'serviceid': service_id}
        )
        return categories

    async def get_task_types(self, service_id: int) -> List[dict]:
        """
        Получает список типов заявок для указанного сервиса.

        :param service_id: Идентификатор сервиса
        :type service_id: int

        :return: Список типов заявок
        :rtype: List[dict]
        """
        data = await self._send_request(
            'GET',
            'tasktype',
            params={'serviceid': service_id}
        )
        return data['TaskTypes']

    async def get_new_task(
            self,
            service_id: int,
            task_type_id: int
    ) -> Tuple[dict, dict, List[dict]]:
        """
        Получает шаблон новой заявки, полномочия пользователя и список
        дополнительных полей заявки для указанного сервиса и типа заявки.

        :param service_id: Идентификатор сервиса
        :type service_id: int
        :param task_type_id: Идентификатор типа заявки
        :type task_type_id: int

        :return: Шаблон новой заявки, полномочия пользователя и список
            дополнительных полей заявки.
        :rtype: Tuple[dict, dict, List[dict]]
        """
        data = await self._send_request(
            'GET',
            'newtask',
            params={
                'serviceid': service_id,
                'tasktypeid': task_type_id,
                'include': 'TASKTYPE,USERTASKRIGHTS'
            }
        )
        return data['Task'], data['Rights'], data['TaskType']['TaskTypeFields']

    async def upload_file(self, file: Path) -> str:
        """
        Загружает файл.

        :param file: Файл
        :type file: Path

        :return: Токен загруженного файла
        :rtype: str
        """
        form_data = FormData(quote_fields=False)
        form_data.add_field(
            'file',
            open(file, 'rb'),
            filename=file.name,
            content_type=get_content_type(file)
        )
        data = await self._send_request(
            'POST',
            'TaskFile',
            data=form_data
        )
        return data['FileTokens']

    async def create_task(self, **kwargs) -> dict:
        """
        Создает новую заявку.

        :param kwargs: Параметры заявки
        :type kwargs: dict

        :return: Новая заявка
        :rtype: dict
        """
        kwargs = clean_none_values(kwargs)
        if settings.DEBUG:
            description = kwargs.get('description', '')
            kwargs['Description'] = 'Создано тестовым ботом!\n' + description
            if kwargs.get('Name'):
                kwargs['Name'] = 'ТЕСТ! ' + kwargs['Name']

        data = await self._send_request(
            'POST',
            'task',
            json=kwargs
        )
        return data['Task']

    async def check_user_can_create_task(
            self,
            service_id: int,
            user_name: str
    ) -> bool:
        data = await self._send_request(
            'GET',
            f'taskcreator',
            params={
                'serviceid': service_id,
                'search': user_name
            }
        )
        return bool(data['Users'])
