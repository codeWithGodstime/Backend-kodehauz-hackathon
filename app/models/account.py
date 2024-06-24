from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic.networks import EmailStr
from sqlmodel import Field, Relationship

from .base import ModelBase
from .enum import BaseEnum


# Need this check to avoid circular loading errors
if TYPE_CHECKING:  # pragma: no cover
    from .profile import Profile, ProfileSmall  # noqa: F401


class AccountStatus(BaseEnum):
    online = "online"
    active = "active"
    suspended = "suspended"
    banned = "banned"

    def isActive(status: "AccountStatus") -> bool:
        return status == AccountStatus.online or status == AccountStatus.active


# class AccountRole(ModelBase, table=True):
#     name: str = Field(unique=True)
#     description: str
#     workspace_id: Optional[int] = Field(foreign_key="workspace.id")


class AccountRole(BaseEnum):
    root = "root"
    admin = "admin"
    user = "user"


# Shared properties
class AccountBase(ModelBase):
    username: str = Field(unique=True, index=True)
    email: EmailStr = Field(unique=True, index=True)
    phone: str = Field(unique=True, index=True)
    status: AccountStatus = AccountStatus.active
    role: AccountRole = AccountRole.user


class Account(AccountBase, table=True):
    hashed_password: Optional[str]
    last_login_date: Optional[datetime]
    profile: "Profile" = Relationship(
        sa_relationship_kwargs={"uselist": False},
        back_populates="account",
    )


# Properties to receive via API on creation
class AccountCreate(AccountBase):
    password: str


class AccountRead(AccountBase):
    id: int


class AccountReadAdmin(ModelBase):
    id: int
    username: str
    email: EmailStr
    phone: str
    status: AccountStatus
    role: AccountRole


class AccountReadPublic(ModelBase):
    id: int
    username: str
    status: AccountStatus
    role: AccountRole


# Properties to receive via API on update
class AccountUpdate(ModelBase):
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None


class AccountReadPublicProfile(AccountReadPublic):
    profile: "ProfileSmall"
