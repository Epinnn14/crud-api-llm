"""The contract, written down before any model is called. Copied from JOB-CARD.md."""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(str, Enum):
    work = "work"
    personal = "personal"
    errand = "errand"
    health = "health"
    finance = "finance"
    other = "other"


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class TriageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000, description="A messy note, 1-1000 characters")

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class Triage(BaseModel):
    """What the endpoint returns, every time, and what the model's answer is validated against."""
    model_config = ConfigDict(extra="forbid")  # an extra field from the model is a failure, not a bonus

    title: str = Field(min_length=3, max_length=80)
    category: Category
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=200)


# LLM_STUB=1 returns this without calling any model: build and debug for free.
STUB = Triage(title="Rebook the dentist appointment", category=Category.health, priority=Priority.normal,
              confidence=0.9, reason="Stub mode: a fixed answer, no model was called.")
