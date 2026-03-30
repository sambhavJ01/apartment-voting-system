from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class VoteInitiateRequest(BaseModel):
    """Step 1: user declares intent; system sends OTP."""
    topic_id: int
    option_id: int


class VoteCastRequest(BaseModel):
    """Step 2: user confirms with OTP → vote is recorded."""
    topic_id: int
    option_id: int
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class VoteResultItem(BaseModel):
    option_id: int
    option_text: str
    vote_count: int
    percentage: float


class VoteResultResponse(BaseModel):
    success: bool
    topic_id: int
    topic_title: str
    mode: str
    status: str
    total_votes: int
    total_eligible: int
    participation_pct: float
    results: List[VoteResultItem]


class VoteCastResponse(BaseModel):
    success: bool
    message: str
    topic_id: Optional[int] = None
    voted_at: Optional[datetime] = None
