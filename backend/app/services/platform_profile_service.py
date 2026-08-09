from sqlalchemy.orm import Session

from app.models.platform_profile import PlatformProfile
from app.repositories.platform_profile_repository import PlatformProfileRepository
from app.schemas.platform_profile import PlatformProfileCreate, PlatformProfileUpdate


class PlatformProfileService:
    def __init__(self, db: Session):
        self.repository = PlatformProfileRepository(db)

    def get_profile(self, profile_id: int) -> PlatformProfile | None:
        return self.repository.get_by_id(profile_id)

    def get_profiles(
        self,
        skip: int,
        limit: int,
        user_id: int | None = None,
    ) -> list[PlatformProfile]:
        if user_id is not None:
            return self.repository.get_by_user(user_id, skip, limit)
        return self.repository.get_all(skip, limit)

    def create_profile(self, data: PlatformProfileCreate) -> PlatformProfile:
        return self.repository.create(PlatformProfile(**data.model_dump()))

    def update_profile(self, profile: PlatformProfile, data: PlatformProfileUpdate) -> PlatformProfile:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        return self.repository.update(profile)

    def delete_profile(self, profile: PlatformProfile) -> None:
        self.repository.delete(profile)
