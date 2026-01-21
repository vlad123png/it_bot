from pydantic import SecretStr
from pydantic_settings import BaseSettings


class DBSettings(BaseSettings):
    """
    Настройки базы данных.

    Найстроки:
    - HOST_NAME (str): хост БД, ip:port
    - USER_NAME (str): имя пользователя в БД
    - USER_PASSWORD (str): пароль пользователя в БД
    - DB_NAME (str): имя БД
    - DB_PORT (str): порт БД
    """
    HOST_NAME: str
    USER_NAME: str
    USER_PASSWORD: SecretStr
    DB_NAME: str
    DB_PORT: str

    class Config:
        env_file = '.env'
        extra = 'ignore'
        validate_assignment = True
