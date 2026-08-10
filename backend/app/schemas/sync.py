from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Platform


class SyncResult(BaseModel):
    """Summary of a completed platform synchronization."""

    profile_id: int
    platform: Platform
    problems_created: int
    contests_created: int
    submissions_created: int
    submissions_skipped: int
    rating_history_created: int
    contest_participations_created: int
    problems_solved: int
    contests_attended: int
    synced_at: datetime
