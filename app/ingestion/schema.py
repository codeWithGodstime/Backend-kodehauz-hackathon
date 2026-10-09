"""Structured extraction result for an inbound customer message."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.socialchef import MessageCategory


class ExtractedOrderItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    quantity: int = 1

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("quantity", mode="before")
    @classmethod
    def coerce_quantity(cls, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return 1
        try:
            number = int(str(value).strip())
        except ValueError:
            return 1
        return number if number > 0 else 1


class MessageExtraction(BaseModel):
    """ORDER, ENQUIRY, or ignore. Field values stay lowercase to match the DB enum."""

    model_config = ConfigDict(extra="ignore")

    category: Literal["order", "enquiry", "ignore"] = "enquiry"
    items: list[ExtractedOrderItem] = Field(default_factory=list)
    delivery_hint: str | None = None
    topic: str | None = None
    question_summary: str | None = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        if text in {"order", "orders"}:
            return "order"
        if text in {"enquiry", "inquiry", "enquiries", "inquiries", "question"}:
            return "enquiry"
        if text == "ignore":
            return "ignore"
        return "enquiry"

    @field_validator("delivery_hint", "topic", "question_summary", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def message_category(self) -> MessageCategory:
        return MessageCategory(self.category)

    def parsed_metadata(self) -> dict[str, Any]:
        if self.category == "order":
            metadata: dict[str, Any] = {
                "items": [
                    {"name": item.name, "quantity": item.quantity}
                    for item in self.items
                    if item.name
                ]
            }
            if self.delivery_hint:
                metadata["delivery_hint"] = self.delivery_hint
            return metadata
        if self.category == "enquiry":
            return {
                "topic": self.topic or "general",
                "question_summary": self.question_summary or "",
            }
        return {"reason": "no_customer_request"}
