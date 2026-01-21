from functools import cache

from .backend_api import BackendAPI
from ..config.settings import settings


@cache
def get_backend_api() -> BackendAPI:
    return BackendAPI(
        base_url=settings.BACKEND_API.BASE_URL,
        login=settings.BACKEND_API.LOGIN,
        password=settings.BACKEND_API.PASSWORD,
        timeout=120,
    )
