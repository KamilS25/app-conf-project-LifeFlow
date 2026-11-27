from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.finance import CurrencyTotals, finance_totals, month_to_date
from app.goals import GoalResponse, get_goal_tasks, goal_response
from app.models import Goal, Task, TaskStatus
from app.security import CurrentUser, DatabaseSession
from app.task_schemas import TaskResponse

router = APIRouter(tags=["Dashboard"])


class Dashboard(BaseModel):
    today: date
    task_counts: dict[TaskStatus, int]
    goal_count: int
    goals: list[GoalResponse]
    upcoming: list[TaskResponse]
    finances: list[CurrencyTotals]


@router.get("/dashboard")
def dashboard(db: DatabaseSession, user: CurrentUser) -> Dashboard:
    counts = dict.fromkeys(TaskStatus, 0)
    for status, count in db.execute(
        select(Task.status, func.count(Task.id))
        .where(Task.owner_id == user.id)
        .group_by(Task.status)
    ):
        counts[TaskStatus(status)] = count
    goals = list(
        db.scalars(
            select(Goal)
            .where(Goal.owner_id == user.id)
            .order_by(Goal.due_date.nulls_last(), Goal.id)
            .limit(3)
        )
    )
    goal_tasks = get_goal_tasks(db, user.id, [goal.id for goal in goals])
    upcoming = db.scalars(
        select(Task)
        .where(
            Task.owner_id == user.id,
            Task.status != TaskStatus.DONE,
            Task.due_date.is_not(None),
        )
        .order_by(Task.due_date, Task.id)
        .limit(5)
    )
    return Dashboard(
        today=datetime.now().date(),
        task_counts=counts,
        goal_count=db.scalar(
            select(func.count(Goal.id)).where(Goal.owner_id == user.id)
        )
        or 0,
        goals=[goal_response(goal, goal_tasks[goal.id]) for goal in goals],
        upcoming=[TaskResponse.model_validate(task) for task in upcoming],
        finances=finance_totals(db, user.id, month_to_date()),
    )
