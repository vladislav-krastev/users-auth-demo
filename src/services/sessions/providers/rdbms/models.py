import typing

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm

from config.auth import OAuth2Provider
from services.sessions import Session
from services.sessions.types import SESSION_TYPE


class BaseModel(sa_orm.DeclarativeBase):
    pass


class SessionModel(BaseModel):
    __tablename__ = "sessions"

    __table_args__ = (
        # probably not needed, but just in case:
        sa.UniqueConstraint("user_id", "created_at", name="_unique_user_and_created_at"),
    )

    id: sa_orm.Mapped[str] = sa_orm.mapped_column(primary_key=True)
    user_id: sa_orm.Mapped[str] = sa_orm.mapped_column(index=True)
    is_valid: sa_orm.Mapped[bool]
    created_at: sa_orm.Mapped[sa.DateTime] = sa_orm.mapped_column(sa.DateTime(timezone=True))
    expires_at: sa_orm.Mapped[sa.DateTime] = sa_orm.mapped_column(sa.DateTime(timezone=True), index=True)
    provider: sa_orm.Mapped[OAuth2Provider | typing.Literal["local"]] = sa_orm.mapped_column(
        sa.Enum(
            *[*[p.value for p in OAuth2Provider], "local"],
            name="session_provider",
            create_constraint=True,
            validate_strings=True,
        )
    )
    type: sa_orm.Mapped[SESSION_TYPE] = sa_orm.mapped_column(
        sa.Enum(
            *typing.get_args(SESSION_TYPE),
            name="session_type",
            create_constraint=True,
            validate_strings=True,
        )
    )

    @staticmethod
    def from_internal(session: Session) -> "SessionModel":
        return SessionModel(
            id=session.id,
            user_id=str(session.user_id),
            is_valid=session.is_valid,
            created_at=session.created_at,
            expires_at=session.expires_at,
            provider=session.provider,
            type=session.type,
        )


# TODO: how would this work with the other session-providers?
# class AuthProvider(__Base):
#     __tablename__ = "auth_providers"

#     id: sa_orm.Mapped[uuid.UUID] = sa_orm.mapped_column(primary_key=True, server_default=sa.func.gen_random_uuid())
#     name: sa_orm.Mapped[str]
