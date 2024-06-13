from typing import Any, Optional

from app.models.base import SchemaBase


class ServerEvent(SchemaBase):
    name: Optional[str] = "message"
    data: Any
