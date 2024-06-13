from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import AccountRead, UserReadPublic


class Token(BaseModel):
    access_token: str
    expires: datetime
    token_type: str
    account: AccountRead
    user: Optional[UserReadPublic]


class TokenPayload(BaseModel):
    sub: Optional[int] = None
