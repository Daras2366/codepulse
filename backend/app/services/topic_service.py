from sqlalchemy.orm import Session

from app.models.topic import Topic
from app.repositories.topic_repository import TopicRepository


class TopicService:
    def __init__(self, db: Session):
        self.repository = TopicRepository(db)

    def get_topic(self, topic_id: int) -> Topic | None:
        return self.repository.get_by_id(topic_id)

    def get_topics(self, skip: int, limit: int) -> list[Topic]:
        return self.repository.get_all(skip, limit)
