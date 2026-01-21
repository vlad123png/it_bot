from enum import StrEnum
from typing import Literal

from aiogram.filters.callback_data import CallbackData

from src.config.ai import STTModel


class ServiceAction(StrEnum):
    select = 'select'
    back = 'back'


class ServiceCallback(CallbackData, prefix='service'):
    action: ServiceAction
    service_id: int
    new_msg: bool = False


class ShowServiceCallback(CallbackData, prefix='show-services'):
    force_new_message: bool = False


class NewTaskCallback(CallbackData, prefix='new-task'):
    service_id: int
    task_type_id: int


class OptionalFieldAction(StrEnum):
    fill = 'fill'
    skip = 'skip'


class OptionalFieldCallback(CallbackData, prefix='optional-field'):
    action: OptionalFieldAction
    task_timestamp: int
    field_key: str


class CheckboxCallback(CallbackData, prefix='checkbox'):
    task_timestamp: int
    field_key: str
    value: bool


class ListCallback(CallbackData, prefix='list'):
    task_timestamp: int
    field_key: str
    option_id: int


class ChoiceSelectCallback(CallbackData, prefix='choice-select'):
    task_timestamp: int
    field_key: str
    option_id: int


class ChoiceCompleteCallback(CallbackData, prefix='choice-complete'):
    task_timestamp: int
    field_key: str


class FilesAction(StrEnum):
    attach = 'attach'
    proceed = 'proceed'


class FilesCallback(CallbackData, prefix='files'):
    action: FilesAction
    task_timestamp: int


class TaskAction(StrEnum):
    send = 'send'
    cancel = 'cancel'


class TaskCallback(CallbackData, prefix='task'):
    action: TaskAction
    task_timestamp: int


class ReactionType(StrEnum):
    like = 'like'
    dislike = 'dislike'


class ReactionCallback(CallbackData, prefix='reaction'):
    id: str
    type: ReactionType


class AnswerFeedbackCallback(CallbackData, prefix='report_answer'):
    id: str


class FeedbackAction(StrEnum):
    leave = 'leave'
    skip = 'skip'


class FeedbackCallback(CallbackData, prefix='feedback'):
    action: FeedbackAction
    id: str


class ConfirmationAction(StrEnum):
    confirm = 'confirm'
    edit = 'edit'
    cancel = 'cancel'


class ConfirmationCallback(CallbackData, prefix='confirmation'):
    action: ConfirmationAction


class AdminAction(StrEnum):
    change_settings = 'change_settings'
    broadcast = 'broadcast'
    add_admin = 'add_admin'
    remove_admin = 'remove_admin'
    testing = 'testing'
    collect_statistics = 'collect_statistics'
    users_sync = 'users_sync'


class AdminCallback(CallbackData, prefix='admin'):
    action: AdminAction


class TypeSettingsAction(StrEnum):
    general = 'general'
    ai = 'ai'
    update_prompts = 'update_prompts'
    update_kwn = 'update_kwn'
    back = 'back'


class CurrentMenu(StrEnum):
    main_settings = 'main'
    general = 'general'
    ai = 'ai'
    update_kwn = 'update_kwn'
    change_prompts = 'change_prompts'
    broadcast = 'broadcast'
    my_active_broadcast = 'my_active_broadcast'
    change_model = 'change_model'


class TypeSettingsCallback(CallbackData, prefix='settings'):
    action: TypeSettingsAction
    current_menu: CurrentMenu


class ChangeSettingsCallback(CallbackData, prefix='parameter'):
    name: str
    subclass_tag: str
    type: str
    value: str


class TimezoneCallback(CallbackData, prefix='timezone'):
    offset: int
    timezone: str


class ChangeSTTModelCallback(CallbackData, prefix='stt_model'):
    name: STTModel


class BroadcastMessageType(StrEnum):
    update_retail_1c = 'retail_1c'
    update_instruction = 'instruction'
    change_process = 'change_process'
    important_info = 'important_info'
    it_news = 'it_news'
    new_survey = 'survey'
    survey_result = 'survey_result'
    my_active_broadcast = 'my_active_broadcast'


class BroadcastCallback(CallbackData, prefix='broadcast'):
    type: BroadcastMessageType


class SurveyChoiceCallback(CallbackData, prefix='survey_choice'):
    choice_id: int


class ConfirmSurveyChoiceCallback(CallbackData, prefix='confirm_survey_choices'):
    survey_id: int


class BroadcastType(StrEnum):
    message = 'msg'
    survey = 'srv'


class MyActiveBroadcastCallback(CallbackData, prefix='my_active_broadcast'):
    type: BroadcastType
    id: int


class ActionBroadcastType(StrEnum):
    edit_text = 'text'
    edit_max_number = 'number'
    edit_choices = 'choices'
    edit_date = 'date'
    delete = 'del'
    back = 'back'


class EditBroadcastCallback(CallbackData, prefix='edit_broadcast'):
    id: int
    action: ActionBroadcastType


class UpdateKnowledgeBasesCallback(CallbackData, prefix='update_kwn'):
    action: Literal['help', 'ared_help', '1c', 'sap_erp', 'document_flow_1c', 'sbis', 'upp', 'all']


class FeedbackType(StrEnum):
    """
    Типы обратной связи от пользователя.

    - SUGGESTION_IDEA: Предложение идеи
    - FEEDBACK: Отзыв о боте
    """
    SUGGESTION_IDEA = 'SUGGESTION_IDEA'
    FEEDBACK = 'FEEDBACK'
