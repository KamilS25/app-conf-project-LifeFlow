from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import ColumnElement, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Task, User
from app.task_schemas import (
    TaskCreate,
    TaskNotFoundResponse,
    TaskResponse,
    TaskUpdate,
    TaskValidationResponse,
)

DEMO_OWNER_EMAIL = "demo@lifeflow.invalid"

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    responses={
        400: {"model": TaskValidationResponse, "description": "Invalid request"},
        "default": {"description": "Unexpected error"},
    },
)

NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": TaskNotFoundResponse, "description": "Task not found"}
}
DatabaseSession = Annotated[Session, Depends(get_session)]
TaskID = Annotated[int, Path(ge=1, le=2_147_483_647)]

demo_owner_id = select(User.id).where(User.email == DEMO_OWNER_EMAIL)
demo_owner_scope = Task.owner_id == demo_owner_id.scalar_subquery()


def get_or_create_demo_owner(session: Session) -> int:
    owner_id = session.scalar(demo_owner_id)
    if owner_id is not None:
        return owner_id

    session.execute(
        insert(User)
        .values(email=DEMO_OWNER_EMAIL)
        .on_conflict_do_nothing(index_elements=[User.email])
    )
    return session.execute(demo_owner_id).scalar_one()


def owned_task(task_id: int) -> ColumnElement[bool]:
    return demo_owner_scope & (Task.id == task_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(data: TaskCreate, session: DatabaseSession) -> TaskResponse:
    """Create a task for the development demo owner."""
    task = Task(owner_id=get_or_create_demo_owner(session), **data.model_dump())
    session.add(task)
    session.flush()
    result = TaskResponse.model_validate(task)
    session.commit()
    return result


@router.get("")
def list_tasks(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
) -> list[TaskResponse]:
    """List the demo owner's tasks in ascending ID order."""
    tasks = session.scalars(
        select(Task)
        .where(demo_owner_scope)
        .order_by(Task.id)
        .offset(offset)
        .limit(limit)
    )
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get("/{task_id}", responses=NOT_FOUND)
def read_task(task_id: TaskID, session: DatabaseSession) -> TaskResponse:
    """Read a task by ID."""
    task = session.scalar(select(Task).where(owned_task(task_id)))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.put("/{task_id}", responses=NOT_FOUND)
def update_task(
    task_id: TaskID, data: TaskUpdate, session: DatabaseSession
) -> TaskResponse:
    """Replace a task's editable fields."""
    task = session.scalar(
        update(Task)
        .where(owned_task(task_id))
        .values(**data.model_dump())
        .returning(Task)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    result = TaskResponse.model_validate(task)
    session.commit()
    return result


@router.delete(
    "/{task_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND
)
def delete_task(task_id: TaskID, session: DatabaseSession) -> Response:
    """Delete a task by ID."""
    deleted_id = session.scalar(
        delete(Task).where(owned_task(task_id)).returning(Task.id)
    )
    if deleted_id is None:
        raise HTTPException(status_code=404, detail="Task not found")
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
