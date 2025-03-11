from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "discord",
                "facebook",
                "github",
                "google",
                "linkedin",
                "microsoft",
                "redit",
                "local",
                name="session_provider",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("type", sa.Enum("cookie", "token", name="session_type", create_constraint=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "created_at", name="_unique_user_and_created_at"),
    )
    op.create_index("ix_session_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_session_expires_at", "sessions", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_session_user_id", "sessions")
    op.drop_index("ix_session_expires_at", "sessions")
    op.drop_table("sessions")
    op.execute("DROP TYPE session_provider")
    op.execute("DROP TYPE session_type")
