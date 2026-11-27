from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Goal, Task, TaskStatus, User
from app.security import (
    CurrentUser,
    DatabaseSession,
    current_user,
    require_request_header,
)
from app.task_schemas import TaskFields

router = APIRouter(
    prefix="/goals",
    tags=["Goals"],
    dependencies=[Depends(current_user), Depends(require_request_header)],
)
GoalID = Annotated[int, Path(ge=1, le=2_147_483_647)]
LinkedTaskID = Annotated[int, Field(ge=1, le=2_147_483_647)]


class GoalInput(TaskFields):
    model_config = ConfigDict(extra="forbid")

    task_ids: Annotated[list[LinkedTaskID], Field(min_length=1)]

    @field_validator("task_ids")
    @classmethod
    def unique_tasks(cls, task_ids: list[int]) -> list[int]:
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Укажите каждую задачу один раз")
        return task_ids


class LinkedTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: TaskStatus


class GoalResponse(TaskFields):
    id: int
    progress: int
    completed_tasks: int
    tasks: list[LinkedTask]


def lock_goal_changes(db: Session, owner_id: int) -> None:
    # Membership changes and task deletions share the same lock for this account.
    db.execute(
        select(User.id).where(User.id == owner_id).with_for_update()
    ).scalar_one()


def get_goal(db: Session, owner_id: int, goal_id: int) -> Goal:
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.owner_id == owner_id))
    if goal is None:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    return goal


def get_goal_tasks(
    db: Session, owner_id: int, goal_ids: list[int]
) -> dict[int, list[Task]]:
    groups: dict[int, list[Task]] = defaultdict(list)
    if goal_ids:
        tasks = db.scalars(
            select(Task)
            .where(Task.owner_id == owner_id, Task.goal_id.in_(goal_ids))
            .order_by(Task.id)
        )
        for task in tasks:
            if task.goal_id is not None:
                groups[task.goal_id].append(task)
    return groups


def goal_response(goal: Goal, tasks: list[Task]) -> GoalResponse:
    completed = sum(task.status == TaskStatus.DONE for task in tasks)
    return GoalResponse(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        due_date=goal.due_date,
        completed_tasks=completed,
        progress=completed * 100 // len(tasks) if tasks else 0,
        tasks=[LinkedTask.model_validate(task) for task in tasks],
    )


def set_goal_tasks(db: Session, goal: Goal, task_ids: list[int]) -> list[Task]:
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.owner_id == goal.owner_id, Task.id.in_(task_ids))
            .order_by(Task.id)
        )
    )
    if len(tasks) != len(task_ids):
        raise HTTPException(
            status_code=404, detail="Одна из выбранных задач не найдена"
        )
    if any(task.goal_id not in {None, goal.id} for task in tasks):
        raise HTTPException(status_code=409, detail="Задача уже связана с другой целью")
    db.execute(
        update(Task)
        .where(
            Task.owner_id == goal.owner_id,
            Task.goal_id == goal.id,
            Task.id.not_in(task_ids),
        )
        .values(goal_id=None)
    )
    for task in tasks:
        task.goal_id = goal.id
    return tasks


def ensure_goal_keeps_a_task(db: Session, task: Task) -> None:
    if task.goal_id is None:
        return
    task_count = db.scalar(
        select(func.count(Task.id)).where(Task.goal_id == task.goal_id)
    )
    if task_count == 1:
        raise HTTPException(
            status_code=409,
            detail="Это последняя задача цели. Добавьте другую задачу или удалите цель.",
        )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_goal(
    data: GoalInput, db: DatabaseSession, user: CurrentUser
) -> GoalResponse:
    lock_goal_changes(db, user.id)
    goal = Goal(owner_id=user.id, **data.model_dump(exclude={"task_ids"}))
    db.add(goal)
    db.flush()
    tasks = set_goal_tasks(db, goal, data.task_ids)
    result = goal_response(goal, tasks)
    db.commit()
    return result


@router.get("")
def list_goals(
    db: DatabaseSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
) -> list[GoalResponse]:
    goals = list(
        db.scalars(
            select(Goal)
            .where(Goal.owner_id == user.id)
            .order_by(Goal.id)
            .offset(offset)
            .limit(limit)
        )
    )
    tasks = get_goal_tasks(db, user.id, [goal.id for goal in goals])
    return [goal_response(goal, tasks[goal.id]) for goal in goals]


@router.get("/{goal_id}")
def read_goal(goal_id: GoalID, db: DatabaseSession, user: CurrentUser) -> GoalResponse:
    goal = get_goal(db, user.id, goal_id)
    return goal_response(goal, get_goal_tasks(db, user.id, [goal.id])[goal.id])


@router.put("/{goal_id}")
def update_goal(
    goal_id: GoalID, data: GoalInput, db: DatabaseSession, user: CurrentUser
) -> GoalResponse:
    lock_goal_changes(db, user.id)
    goal = get_goal(db, user.id, goal_id)
    tasks = set_goal_tasks(db, goal, data.task_ids)
    goal.title = data.title
    goal.description = data.description
    goal.due_date = data.due_date
    result = goal_response(goal, tasks)
    db.commit()
    return result


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: GoalID, db: DatabaseSession, user: CurrentUser) -> Response:
    lock_goal_changes(db, user.id)
    goal = get_goal(db, user.id, goal_id)
    db.execute(
        update(Task)
        .where(Task.owner_id == user.id, Task.goal_id == goal.id)
        .values(goal_id=None)
    )
    db.delete(goal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
