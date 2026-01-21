from src import messages


class APIError(Exception):
  """
  Исключение, возникающее при ошибке взаимодействия с API.
  """
  error_message = messages.SERVICE_UNAVAILABLE_MESSAGE

  def __init__(self, message: str) -> None:
    self.message = message
    super().__init__(self.format_error_message())

  def format_error_message(self) -> str:
    return f'APIError: {self.message}'


class ClientError(Exception):
  """
  Исключение, возникающее при ошибке обработки ответа API.
  """

  def __init__(
      self,
      status: int,
      message: str,
      message_detail: str = None
  ) -> None:
    self.status = status
    self.message = message
    self.message_detail = message_detail
    super().__init__(self.format_error_message())

  def format_error_message(self) -> str:
    msg = f'ClientError: {self.status}, Message: {self.message}'
    if self.message_detail:
      msg += f', Message Detail: {self.message_detail}'
    return msg


class APIPermissionError(APIError):
  ...
