from src import messages


class TaskError(Exception):
    """Базовый класс для ошибок, связанных с заявкой."""
    error_message = messages.TASK_ERROR_MESSAGE


class NewTaskError(TaskError):
    """Исключение, возникающее при ошибке получения шаблона новой заявки."""
    error_message = messages.NEW_TASK_ERROR_MESSAGE


class UploadFileError(TaskError):
    """Исключение, возникающее при ошибке загрузки файла."""
    error_message = messages.CREATE_TASK_ERROR_MESSAGE


class CreateTaskError(TaskError):
    """Исключение, возникающее при ошибке создания новой заявки."""
    error_message = messages.CREATE_TASK_ERROR_MESSAGE


class KnowledgeBaseNotFoundError(Exception):
    """Исключение для ошибок загрузки базы знаний."""


class LoadPromptError(Exception):
    """Исключение для ошибок при загрузке промптов. """


class KnowledgeBaseError(Exception):
    """Исключения для ошибок при работе с БЗ"""

    def __init__(self, message: str, show_traceback: bool = True):
        self.show_traceback = show_traceback
        super().__init__(message)
