from typing import Literal

from pydantic import BaseModel, Field


class CopilotHistoryMessage(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(..., min_length=1, max_length=4000)


class CopilotRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[CopilotHistoryMessage] = Field(default_factory=list, max_length=12)
