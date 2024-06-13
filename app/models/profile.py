from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from .base import ModelBase, SchemaBase
from .enum import BaseEnum

# Need this check to avoid circular loading errors
if TYPE_CHECKING:  # pragma: no cover
    from .account import Account  # noqa: F401
    from .address import Address


class Gender(BaseEnum):
    male = "male"
    female = "female"
    other = "other"


class MaritalStatus(BaseEnum):
    single = "single"
    married = "married"
    other = "other"


# Shared properties
class ProfileBase(ModelBase):
    id: int = Field(primary_key=True, foreign_key="account.id")
    first_name: Optional[str] = Field(index=True)
    last_name: Optional[str] = Field(index=True)
    date_of_birth: Optional[date]
    gender: Optional[Gender]
    marital_status: Optional[MaritalStatus]


# Model to be persisted in the database (note the table=True)
class Profile(ProfileBase, table=True):
    account: "Account" = Relationship(back_populates="profile")
    address: Optional["Address"] = Relationship(back_populates="owner")
    avatar: Optional[str]


# Properties to receive on item creation - same as base, no changes
class ProfileCreate(SchemaBase):
    first_name: Optional[str]
    last_name: Optional[str]
    date_of_birth: Optional[date]
    gender: Optional[Gender]
    marital_status: Optional[MaritalStatus]


# Properties to receive on item update - make them optional
class ProfileUpdate(ProfileCreate):
    pass


class ProfileRead(SchemaBase):
    id: int
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Optional[Gender]
    marital_status: Optional[MaritalStatus]
    avatar: Optional[str]


class ProfileInfoRead(SchemaBase):
    id: int
    employment_status: Optional[str]
    qualification: Optional[str]
    information_source: Optional[str]


class ProfileCategoryRead(SchemaBase):
    id: int
    level_id: int
    track_id: int
    stage_id: Optional[int]


# @todo: Separate profile available to all public from what's available
# to admin or trainers.
class UserProfile(SchemaBase):
    id: int
    username: str
    email: str
    phone: str
    profile: Optional[ProfileRead]
    student: Optional[ProfileCategoryRead]
    trainer: Optional[ProfileCategoryRead]
    info: Optional[ProfileInfoRead]


class ProfileSmall(SchemaBase):
    id: int
    first_name: str
    last_name: str
    gender: Optional[Gender]
    avatar: Optional[str]
