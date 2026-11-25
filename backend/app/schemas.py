
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: Optional[str] = Field(
        default=None,
        max_length=4000
    )

    def validate_message(self):
        if not self.message.strip():
            raise ValueError("Message cannot be empty")


class ChatMetadata(BaseModel):
    resolution_source: Literal[
        "LIVE_INFERENCE",
        "LLM_CACHE"
    ]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]
    fallback_attempts: int


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata
