from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from pydantic.networks import EmailStr
from sqlmodel import Field, Relationship

from .base import ModelBase
from .enum import BaseEnum
from .user import User
from .workspace import WorkspaceRead

# Need this check to avoid circular loading errors
if TYPE_CHECKING:  # pragma: no cover
    from .document import Document  # noqa: F401
    from .profile import Profile, ProfileSmall  # noqa: F401
    from .student import Student  # noqa: F401
    from .submission import Submission  # noqa: F401
    from .trainer import Trainer  # noqa: F401
    from .userinfo import UserInfo  # noqa: F401
    from .workspace import Workspace  # noqa: F401


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
    users: List["User"] = Relationship()
    current_workspace_id: Optional[int] = Field(foreign_key="workspace.id")
    currentWorkspace: "Workspace" = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "Account.current_workspace_id==Workspace.id",
            "lazy": "joined",
        }
    )
    workspaces: List["Workspace"] = Relationship(
        # back_populates="accounts",
        link_model=User,
        # sa_relationship_args='overlaps="accounts,users"',
        # sa_relationship_kwargs={"overlaps": "accounts,users"},
    )


# Properties to receive via API on creation
class AccountCreate(AccountBase):
    password: str


class AccountRead(AccountBase):
    id: int
    currentWorkspace: Optional[WorkspaceRead]
    workspaces: List[WorkspaceRead]


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
