from src import messages


class SendEmailError(Exception):
    """Исключение, возникающее при ошибке отправки e-mail."""
    error_message = messages.EMAIL_SEND_ERROR_MESSAGE
