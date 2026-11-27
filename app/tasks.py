from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import ColumnElement, select, update

from app.goals import ensure_goal_keeps_a_task, lock_goal_changes
from app.models import Task, TaskStatus
from app.security import (
    CurrentUser,
    DatabaseSession,
    current_user,
    require_request_header,
)
from app.task_schemas import (
    TaskCreate,
    TaskNotFoundResponse,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
    TaskValidationResponse,
)

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    dependencies=[Depends(current_user), Depends(require_request_header)],
    responses={
        400: {"model": TaskValidationResponse, "description": "Invalid request"},
        "default": {"description": "Unexpected error"},
    },
)

NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": TaskNotFoundResponse, "description": "Task not found"}
}
TaskID = Annotated[int, Path(ge=1, le=2_147_483_647)]


def owned_task(task_id: int, owner_id: int) -> ColumnElement[bool]:
    return (Task.owner_id == owner_id) & (Task.id == task_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate, session: DatabaseSession, user: CurrentUser
) -> TaskResponse:
    """Create a task for the signed-in account."""
    task = Task(owner_id=user.id, **data.model_dump())
    session.add(task)
    session.flush()
    result = TaskResponse.model_validate(task)
    session.commit()
    return result


@router.get("")
def list_tasks(
    session: DatabaseSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
) -> list[TaskResponse]:
    """List the signed-in account's tasks in ascending ID order."""
    query = select(Task).where(Task.owner_id == user.id)
    if task_status is not None:
        query = query.where(Task.status == task_status.value)
    tasks = session.scalars(query.order_by(Task.id).offset(offset).limit(limit))
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get("/{task_id}", responses=NOT_FOUND)
def read_task(
    task_id: TaskID, session: DatabaseSession, user: CurrentUser
) -> TaskResponse:
    """Read a task by ID."""
    task = session.scalar(select(Task).where(owned_task(task_id, user.id)))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.put("/{task_id}", responses=NOT_FOUND)
def update_task(
    task_id: TaskID, data: TaskUpdate, session: DatabaseSession, user: CurrentUser
) -> TaskResponse:
    """Replace a task's editable fields."""
    task = session.scalar(
        update(Task)
        .where(owned_task(task_id, user.id))
        .values(**data.model_dump())
        .returning(Task)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    result = TaskResponse.model_validate(task)
    session.commit()
    return result


@router.patch("/{task_id}/status", responses=NOT_FOUND)
def change_task_status(
    task_id: TaskID, data: TaskStatusUpdate, session: DatabaseSession, user: CurrentUser
) -> TaskResponse:
    """Move a task without overwriting its other fields."""
    task = session.scalar(
        update(Task)
        .where(owned_task(task_id, user.id))
        .values(status=data.status)
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
def delete_task(
    task_id: TaskID, session: DatabaseSession, user: CurrentUser
) -> Response:
    """Delete a task by ID."""
    lock_goal_changes(session, user.id)
    task = session.scalar(select(Task).where(owned_task(task_id, user.id)))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    ensure_goal_keeps_a_task(session, task)
    session.delete(task)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
