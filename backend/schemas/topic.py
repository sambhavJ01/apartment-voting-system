from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from backend.models.topic import VotingMode, TopicStatus


# ─── Create / Update ──────────────────────────────────────────────────────────

class OptionIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    order: int = Field(default=0, ge=0)


class TopicCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    mode: VotingMode
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    options: List[OptionIn] = Field(..., min_length=2, max_length=10)
    # User IDs of approved residents appointed as election observers
    observer_ids: List[int] = Field(default_factory=list)


class TopicStatusUpdate(BaseModel):
    status: TopicStatus


class TopicObserverUpdate(BaseModel):
    """Replace the full observer list for a topic."""
    observer_ids: List[int]


# ─── Responses ────────────────────────────────────────────────────────────────

class OptionOut(BaseModel):
    id: int
    text: str
    order: int

    model_config = {"from_attributes": True}


class TopicOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    mode: VotingMode
    status: TopicStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    created_at: datetime
    options: List[OptionOut]

    model_config = {"from_attributes": True}


class TopicSummary(BaseModel):
    topic_id: int
    title: str
    mode: str
    status: str
    total_votes: int
    total_eligible: int
    participation_pct: float
