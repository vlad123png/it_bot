from pydantic_settings import BaseSettings


class BackendAPISettings(BaseSettings):
    """
    Настройки backend api.
    """

    BASE_URL: str
    LOGIN: str
    PASSWORD: str

    class Config:
        env_file = '.env'
        extra = 'ignore'
        validate_assignment = True
        env_prefix = 'BACKEND_API__'
