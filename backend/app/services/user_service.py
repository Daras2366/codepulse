from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate

from app.core.security import hash_password

class UserService:

    @staticmethod
    def create_user(db: Session, user_data: UserCreate):

        existing = UserRepository.get_by_email(db, user_data.email)

        if existing:
            raise ValueError("Email already registered")

        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=hash_password(user_data.password)
        )

        return UserRepository.create(db, user)