from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_logins",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
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
                name="user_login_provider",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="_unique_user_and_provider"),
    )
    op.create_index("ix_users_logins_user_ids", "user_logins", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_logins_user_ids", "user_logins")
    op.drop_table("user_logins")
    op.execute("DROP TYPE user_login_provider")
