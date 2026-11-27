"""Add goals linked to tasks and transactions in four currencies."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("id", "owner_id", name="uq_goals_id_owner"),
    )
    op.create_index("ix_goals_owner_id_id", "goals", ["owner_id", "id"])
    op.add_column("tasks", sa.Column("goal_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_goal_owner",
        "tasks",
        "goals",
        ["goal_id", "owner_id"],
        ["id", "owner_id"],
    )
    op.create_index("ix_tasks_goal_id", "tasks", ["goal_id"])

    op.create_table(
        "finance_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(7), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("kind IN ('income', 'expense')", name="ck_finance_kind"),
        sa.CheckConstraint(
            "currency IN ('RUB', 'USD', 'EUR', 'CNY')", name="ck_finance_currency"
        ),
        sa.CheckConstraint("amount > 0", name="ck_finance_amount_positive"),
    )
    op.create_index(
        "ix_finance_owner_date_id",
        "finance_transactions",
        ["owner_id", "occurred_on", "id"],
    )


def downgrade() -> None:
    op.drop_table("finance_transactions")
    op.drop_constraint("fk_tasks_goal_owner", "tasks", type_="foreignkey")
    op.drop_column("tasks", "goal_id")
    op.drop_table("goals")
