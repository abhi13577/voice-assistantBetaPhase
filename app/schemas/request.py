from pydantic import BaseModel, Field, field_validator, UUID4
from typing import Optional, Dict
from uuid import UUID
from app.core.config import DEMO_USER_ID


class VoiceRequest(BaseModel):
    transcript: Optional[str] = Field(
        default="",
        description="User spoken or typed input",
        max_length=500
    )

    user_id: int = Field(
        ...,
        ge=1,
        description="User ID (required, must be positive)"
    )

    project_id: int = Field(
        ...,
        ge=1,
        description="Project ID (required, must be positive)"
    )

    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Conversation session identifier (required, UUID format recommended)"
    )

    context_summary: Optional[Dict] = Field(
        default=None,
        description="Optional context passed from frontend"
    )

    # 🔥 PRODUCTION VALIDATION (VERY IMPORTANT)
    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, value: Optional[str]) -> str:
        if value is None:
            return ""

        value = value.strip()

        # Prevent empty or meaningless input
        if len(value) == 0:
            return ""

        # Normalize text (production-grade cleanup)
        return value.lower()

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, value: Optional[str]) -> Optional[str]:
        if value:
            return value.strip()
        return value