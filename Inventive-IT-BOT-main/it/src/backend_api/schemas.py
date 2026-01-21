import datetime
from uuid import UUID

from pydantic import model_validator, BaseModel

from src.utils.schemas import InputApiSchema, OutputApiSchema
from .enums import ReactionType


class BackendUserSchema(InputApiSchema):
    id: UUID
    ext_user_id: int | None = None
    role: str
    email: str
    name: str
    surname: str
    messages_limit: int
    work_position: str = ""
    department: str = ""
    is_active: bool

    created_at: datetime.datetime
    updated_at: datetime.datetime


class RetailMessagesSchema(InputApiSchema):
    id: UUID
    user_id: UUID | None
    external_id: int | None
    role: str
    is_answer: bool
    content: str
    current_topic: str | None = None
    images: list[str] | None
    input_tokens: int
    output_tokens: int
    task_id: int | None = None
    updated_at: datetime.datetime
    created_at: datetime.datetime


class CreateRetailMessagesSchema(OutputApiSchema):
    user_id: UUID | None = None
    external_id: int | None = None
    content: str
    is_ared: bool

    @model_validator(mode='after')
    def check_one_of_ids(self) -> 'CreateRetailMessagesSchema':
        provided = [v for v in (self.user_id, self.external_id) if v is not None]
        if len(provided) != 1:
            raise ValueError('Exactly one of user_id or external_id must be provided')
        return self


class RetailFeedbackSchema(InputApiSchema):
    id: UUID
    user_id: UUID | None = None
    external_id: int | None = None
    content: str
    updated_at: datetime.datetime
    created_at: datetime.datetime


class CreateRetailFeedbackSchema(OutputApiSchema):
    user_id: UUID | None = None
    external_id: int | None = None
    content: str

    @model_validator(mode='after')
    def check_one_of_ids(self) -> 'CreateRetailFeedbackSchema':
        provided = [v for v in (self.user_id, self.external_id) if v is not None]
        if len(provided) != 1:
            raise ValueError('Exactly one of user_id or external_id must be provided')
        return self


class RetailMessageFeedbackSchema(InputApiSchema):
    id: UUID
    retail_message_id: UUID
    reaction: ReactionType | None
    content: str | None = None
    updated_at: datetime.datetime
    created_at: datetime.datetime


class CreateRetailMessageFeedbackSchema(OutputApiSchema):
    retail_message_id: UUID | str
    reaction: ReactionType | None = None
    content: str | None = None

    @model_validator(mode='after')
    def check_content_or_reaction(self) -> 'CreateRetailMessageFeedbackSchema':
        if self.reaction is None and self.content is None:
            raise ValueError('Either reaction or content must be provided')
        return self


class TaskStatusSchema(InputApiSchema):
    status: str
    result_id: str | None = None


class DownloadedFile(BaseModel):
    content: bytes
    content_type: str
    extension: str
    content_length: int
    last_modified: str | None = None


class RetailStatistic(InputApiSchema):
    like_count: int  # Количество лайков на ответах ИИ
    dislike_count: int  # Количество дизлайков на ответах ИИ
    user_messages_count: int  # Общее количество сообщений пользователей (вопросы + ответы на уточнения)
    clarify_count: int  # Количество уточняющих вопросов
    answers_count: int  # Количество ответов ИИ (без уточнений)
    input_token_count: int  # Количество затраченных токенов на промпт
    output_token_count: int  # Количество сгенерированных токенов ИИ
