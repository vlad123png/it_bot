from pydantic import SecretStr
from pydantic_settings import BaseSettings


class RedisSettings(BaseSettings):
    """
    Настройки базы данных.

    Найстроки:
    - HOST (str): хост БД
    - PORT (int): порт БД
    - PASSWORD (str): пароль в БД
    - DB_NAME (int): имя БД
    """
    HOST: str
    PORT: int
    USER: str = 'default'
    PASSWORD: SecretStr
    DB: int

    @property
    def redis_url(self):
        password_part = f'{self.USER}:{self.PASSWORD}@' if self.PASSWORD else ''
        return f'redis://{password_part}{self.HOST}:{self.PORT}/{self.DB}'

    class Config:
        env_file = '.env'
        extra = 'ignore'
        validate_assignment = True
        env_prefix = 'REDIS_'