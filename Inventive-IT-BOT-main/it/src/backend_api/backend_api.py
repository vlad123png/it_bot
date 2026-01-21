import asyncio
import datetime as dt
import logging
import mimetypes
import os
from typing import Any, Callable

import aiofiles
from aiohttp import ClientSession, MultipartWriter, ClientTimeout, ClientResponse

from .enums import Index
from .error import (
    AuthError,
    RequestError,
    AnalyzeError,
    AlreadyExistsError,
)
from .schemas import (
    BackendUserSchema,
    TaskStatusSchema,
    RetailMessagesSchema,
    CreateRetailMessagesSchema,
    CreateRetailFeedbackSchema,
    RetailFeedbackSchema,
    CreateRetailMessageFeedbackSchema,
    RetailMessageFeedbackSchema,
    DownloadedFile,
    RetailStatistic,
)

logger = logging.getLogger(__name__)


class BackendAPI:
    """
    Thread-safe (per-process) async client для внутреннего backend-сервиса.
    Один экземпляр на процесс => создавать через factory `get_backend_api()`.
    """

    def __init__(
            self,
            base_url: str,
            login: str,
            password: str,
            timeout: float = 30.0,
            use_ssl: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._login = login
        self._password = password

        # HTTP-клиент с таймаутами
        self._session = ClientSession(
            timeout=ClientTimeout(total=timeout, sock_read=30),
            headers={"User-Agent": "inventive"},
        )
        self._lock = asyncio.Lock()

        # состояние токенов
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._access_expires_at: dt.datetime | None = None
        self._refresh_expires_at: dt.datetime | None = None
        self._use_ssl = use_ssl

    async def close(self) -> None:
        if not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "BackendAPI":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    def _save_tokens(self, payload: dict[str, Any]) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        self._access_token = payload["access_token"]
        self._refresh_token = payload["refresh_token"]
        self._access_expires_at = now + dt.timedelta(
            seconds=payload.get("expires_in", 24 * 3600)
        )
        self._refresh_expires_at = now + dt.timedelta(
            seconds=payload.get("refresh_expires_in", 14 * 24 * 3600)
        )

    async def _authenticate(self) -> None:
        url = f"{self._base_url}/auth/login"
        async with self._session.post(
                url,
                json={"email": self._login, "password": self._password},
                ssl=self._use_ssl,
        ) as resp:
            payload = await resp.json()
            if resp.status != 200:
                raise AuthError(payload)
            self._save_tokens(payload)
            logger.info("Authenticated successfully")

    async def _refresh_access_token(self) -> None:
        if (
                not self._refresh_token
                or dt.datetime.now(dt.timezone.utc) > self._refresh_expires_at
        ):
            await self._authenticate()
            return

        url = f"{self._base_url}/auth/refresh"
        async with self._session.post(
                url, json={"refreshToken": self._refresh_token}, ssl=self._use_ssl
        ) as resp:
            payload = await resp.json()
            if resp.status != 200:
                raise AuthError(payload)
            self._save_tokens(payload)
            logger.info("Access token refreshed")

    async def _ensure_token(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        if self._access_token and now < self._access_expires_at:
            return
        async with self._lock:
            if self._access_token and now < self._access_expires_at:
                return
            if self._refresh_token and now < self._refresh_expires_at:
                await self._refresh_access_token()
            else:
                await self._authenticate()

    async def _request(
            self,
            method: str,
            endpoint: str,
            *,
            json: dict[str, Any] | None = None,
            params: dict[str, Any] | None = None,
            row: bool = False,
            no_response_body: bool = False,
            **kwargs: Any,
    ) -> dict[str, Any] | tuple[ClientResponse, bytes] | None:
        await self._ensure_token()

        url = f"{self._base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        async with self._session.request(
                method,
                url,
                json=json,
                params=params,
                headers=headers,
                ssl=self._use_ssl,
                **kwargs,
        ) as resp:
            if resp.status == 401:
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self._access_token}"
                async with self._session.request(
                        method, url, json=json, params=params, headers=headers, **kwargs,
                ) as retry_resp:
                    resp = retry_resp

            if resp.status == 409:
                raise AlreadyExistsError()
            if resp.status < 200 or resp.status >= 300:
                raise RequestError(await resp.text())

            if row:
                return resp, await resp.read()

            if no_response_body:
                return None

            return await resp.json()

    async def get_users_by_email(self, email: str) -> list[BackendUserSchema]:
        data = await self._request("GET", "/users", params={"email": email})
        return [
            BackendUserSchema.model_validate(u, from_attributes=True)
            for u in data.get("objects", [])
        ]

    async def get_task_status(self, task_id: str) -> TaskStatusSchema:
        data = await self._request("GET", f"/tasks/{task_id}/status")
        return TaskStatusSchema(**data)

    async def upload_file(self, file_path: str) -> str:
        await self._ensure_token()
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"
        filename = os.path.basename(file_path)
        async with aiofiles.open(file_path, "rb") as f:
            file_bytes = await f.read()

        return await self._upload_bytes(file_bytes, filename, content_type)

    async def upload_file_bytes(
            self,
            file_bytes: bytes,
            filename: str,
            content_type: str | None = None,
    ) -> str:
        await self._ensure_token()
        content_type = content_type or mimetypes.guess_type(filename)[0]
        if not content_type:
            content_type = "application/octet-stream"
        return await self._upload_bytes(file_bytes, filename, content_type)

    async def _upload_bytes(
            self, file_bytes: bytes, filename: str, content_type: str
    ) -> str:
        url = f"{self._base_url}/files/upload"

        def _build_mp() -> MultipartWriter:
            mp = MultipartWriter("form-data")
            part = mp.append(file_bytes)
            part.set_content_disposition("form-data", name="file", filename=filename)
            part.headers["Content-Type"] = content_type
            return mp

        # первый запрос
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with self._session.post(url, data=_build_mp(), headers=headers) as resp:
            if resp.status == 401:
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self._access_token}"
                # второй запрос с новым токеном и новым MultipartWriter
                async with self._session.post(
                        url, data=_build_mp(), headers=headers
                ) as retry_resp:
                    resp = retry_resp

            if resp.status != 200:
                raise RequestError(await resp.text())
            return (await resp.json())["id"]

    async def _wait_result(self, task_id: str, fetcher: Callable):
        """Ожидаем SUCCESS с экспоненциальным backoff."""
        delay = 1
        max_delay = 8
        while True:
            status = await self.get_task_status(task_id)
            if status.status == "SUCCESS":
                return await fetcher(status.result_id)
            if status.status in {"PENDING", "STARTED", "RECEIVED", "RETRY", "REQUIRED"}:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
            else:
                raise AnalyzeError(f"Task failed with status {status.status}")

    async def generate_retail_answer(self, data: CreateRetailMessagesSchema) -> RetailMessagesSchema:
        result = await self._request("POST", "/retail-assistant/answer",
                                     json=data.model_dump(by_alias=True, mode="json"), timeout=ClientTimeout(total=500))
        return RetailMessagesSchema(**result)

    async def send_retail_message_feedback(self,
                                           data: CreateRetailMessageFeedbackSchema) -> RetailMessageFeedbackSchema:
        result = await self._request(
            "POST",
            "/retail-assistant/messages-feedbacks",
            json=data.model_dump(by_alias=True, exclude_unset=True, mode="json"),
        )
        return RetailMessageFeedbackSchema(**result)

    async def send_retail_feedback(self, data: CreateRetailFeedbackSchema) -> RetailFeedbackSchema:
        result = await self._request(
            "POST",
            "/retail-assistant/feedbacks",
            json=data.model_dump(by_alias=True, exclude_unset=True, mode="json"),
        )
        return RetailFeedbackSchema(**result)

    async def download_teamly_file(self, link: str) -> DownloadedFile:
        params = {'link': link}
        response, content = await self._request("GET", '/files/teamly', params=params, row=True)
        meta = response.headers
        return DownloadedFile(
            content=content,
            content_type=meta.get("Content-Type"),
            content_length=int(meta.get("Content-Length", 0)),
            extension=meta.get("Extension"),
            last_modified=meta.get("Last-Modified")
        )

    async def update_prompts(self) -> None:
        params = {'assistant': 'retail'}
        await self._request("POST", '/prompts/sync_assistant_prompts', params=params, no_response_body=True)

    async def recreate_index(self, index: Index) -> None:
        params = {'index': index.value}
        await self._request('POST', '/admin/recreate-index', params=params, no_response_body=True)

    async def get_retail_statistics(self, start_time: dt.datetime, end_time: dt.datetime) -> RetailStatistic:
        params = {'start_time': start_time.isoformat(), 'end_time': end_time.isoformat()}
        statistics = await self._request('GET', '/retail-assistant/statistic', params=params)
        return RetailStatistic(**statistics)
