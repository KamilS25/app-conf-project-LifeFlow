from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import TaskStatus


class TaskFields(BaseModel):
    title: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00]*$"
        ),
        Field(examples=["Подготовить демо LifeFlow"]),
    ]
    description: Annotated[str, StringConstraints(pattern=r"^[^\x00]*$")] | None = (
        Field(default=None, examples=["Сверить сценарий показа"])
    )
    due_date: date | None = Field(default=None, examples=["2026-12-01"])


class TaskCreate(TaskFields):
    model_config = ConfigDict(extra="forbid")

    status: TaskStatus = TaskStatus.TODO


class TaskUpdate(TaskFields):
    model_config = ConfigDict(extra="forbid")

    status: TaskStatus


class TaskResponse(TaskFields):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    status: TaskStatus = Field(examples=[TaskStatus.IN_PROGRESS])


class TaskValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class TaskValidationResponse(BaseModel):
    detail: list[TaskValidationIssue]


class TaskNotFoundResponse(BaseModel):
    detail: str = Field(examples=["Task not found"])
