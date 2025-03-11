import uuid
from datetime import datetime

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm

from config.auth import OAuth2Provider
from services.users import BaseUser
from services.users.types import USER_LOGIN_PROVIDER

from .types import CustomDateTime


class BaseModel(sa_orm.DeclarativeBase):
    pass


class UserModel(BaseModel):
    __tablename__ = "users"

    id: sa_orm.Mapped[uuid.UUID] = sa_orm.mapped_column(primary_key=True, server_default=sa.func.gen_random_uuid())
    email: sa_orm.Mapped[str] = sa_orm.mapped_column(nullable=True, index=True)
    username: sa_orm.Mapped[str] = sa_orm.mapped_column(unique=True)
    password: sa_orm.Mapped[str | None] = sa_orm.mapped_column(nullable=True)
    is_admin: sa_orm.Mapped[bool]
    is_admin_super: sa_orm.Mapped[bool]
    logins: sa_orm.Mapped[list["UserLoginModel"]] = sa_orm.relationship(
        back_populates="user",
        # lazy="joined",
    )
    created_at: sa_orm.Mapped[sa.DateTime] = sa_orm.mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    updated_at: sa_orm.Mapped[sa.DateTime] = sa_orm.mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
    )
    is_deleted: sa_orm.Mapped[bool]
    deleted_at: sa_orm.Mapped[datetime] = sa_orm.mapped_column(CustomDateTime(timezone=True))

    @staticmethod
    def from_internal(user: BaseUser) -> "UserModel":
        return UserModel(
            email=user.email,
            username=user.username,
            password=user.password,
            is_admin=user.is_admin,
            is_admin_super=user.is_admin_super,
            is_deleted=user.is_deleted,
            deleted_at=user.deleted_at,
        )

    def to_internal[T: BaseUser](self, model: type[T], /) -> T:
        m = model.model_validate(self, from_attributes=True)
        # m.logins_from.extend(ul.provider for ul in self.logins)
        return m


class UserLoginModel(BaseModel):
    __tablename__ = "user_logins"

    __table_args__ = (sa.UniqueConstraint("user_id", "provider", name="_unique_user_and_provider"),)

    id: sa_orm.Mapped[uuid.UUID] = sa_orm.mapped_column(primary_key=True, server_default=sa.func.gen_random_uuid())
    user_id: sa_orm.Mapped[uuid.UUID] = sa_orm.mapped_column(sa.ForeignKey("users.id"))
    user: sa_orm.Mapped["UserModel"] = sa_orm.relationship(back_populates="logins")
    provider: sa_orm.Mapped[USER_LOGIN_PROVIDER] = sa_orm.mapped_column(
        sa.Enum(
            *[*[p.value for p in OAuth2Provider], "local"],
            name="user_login_provider",
            create_constraint=True,
            validate_strings=True,
        )
    )

    @staticmethod
    def from_internal(user: BaseUser, provider: USER_LOGIN_PROVIDER) -> "UserLoginModel":
        return UserLoginModel(
            user_id=(user.id),
            provider=provider,
        )
