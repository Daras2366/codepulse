from typing import List

from sqlalchemy.orm import Session

from app.models.enums import Platform
from app.models.platform_profile import PlatformProfile
from app.repositories.base import BaseRepository


class PlatformProfileRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, profile: PlatformProfile) -> PlatformProfile:
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_by_id(self, profile_id: int) -> PlatformProfile | None:
        return (
            self.db.query(PlatformProfile)
            .filter(PlatformProfile.id == profile_id)
            .first()
        )

    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PlatformProfile]:
        return (
            self.db.query(PlatformProfile)
            .filter(PlatformProfile.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_platform(
        self,
        user_id: int,
        platform: Platform,
    ) -> PlatformProfile | None:
        return (
            self.db.query(PlatformProfile)
            .filter(
                PlatformProfile.user_id == user_id,
                PlatformProfile.platform == platform,
            )
            .first()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PlatformProfile]:
        return (
            self.db.query(PlatformProfile)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, profile: PlatformProfile) -> PlatformProfile:
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete(self, profile: PlatformProfile) -> None:
        self.db.delete(profile)
        self.db.commit()

    def exists(self, profile_id: int) -> bool:
        return (
            self.db.query(PlatformProfile)
            .filter(PlatformProfile.id == profile_id)
            .first()
            is not None
        )
