from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, AliasGenerator, ConfigDict
from pydantic.alias_generators import to_camel


class InputApiSchema(BaseModel):
    """
    Входная API схема.
    """

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
        )
    )


class OutputApiSchema(BaseModel):
    """
    Выходная API схема.
    """

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        )
    )


class TimeStampsSchema(BaseModel):
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")
