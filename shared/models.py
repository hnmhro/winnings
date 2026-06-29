"""Gemeinsame Datenmodelle für alle Services."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ContestStatus(str, Enum):
    FOUND = "found"
    QUEUED = "queued"
    PARTICIPATING = "participating"
    DONE = "done"
    WON = "won"
    LOST = "lost"
    SKIPPED = "skipped"
    ERROR = "error"


class ParticipationType(str, Enum):
    FORM = "form"
    EMAIL = "email"
    SOCIAL = "social"
    UNKNOWN = "unknown"


class EmailClassification(str, Enum):
    WIN_NOTIFICATION = "WIN_NOTIFICATION"
    CONFIRMATION = "CONFIRMATION"
    NEWSLETTER = "NEWSLETTER"
    SPAM = "SPAM"
    UNKNOWN = "UNKNOWN"


@dataclass
class Contest:
    url: str
    title: str | None = None
    source: str | None = None
    prize_description: str | None = None
    estimated_value: float | None = None
    deadline: datetime | None = None
    participation_type: ParticipationType = ParticipationType.UNKNOWN
    trust_score: float = 0.0
    requirements: list[str] = field(default_factory=list)
    status: ContestStatus = ContestStatus.FOUND
    id: UUID | None = None


@dataclass
class EmailEntry:
    message_id: str
    subject: str
    sender: str
    raw_body: str
    classification: EmailClassification = EmailClassification.UNKNOWN
    contest_id: UUID | None = None
    win_description: str | None = None
    win_value: float | None = None
    action_required: str | None = None
    action_deadline: datetime | None = None
    notified: bool = False


# Redis Queue-Namen
QUEUE_CONTEST_FOUND = "queue:contest:found"
QUEUE_PARTICIPATION = "queue:participation"
QUEUE_NOTIFY = "queue:notify"
QUEUE_EMAIL_CLASSIFY = "queue:email:classify"


@dataclass
class QueueMessage:
    type: str
    payload: dict[str, Any]
    priority: int = 5
