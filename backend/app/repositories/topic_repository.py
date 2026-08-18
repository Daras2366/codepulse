from typing import List

from sqlalchemy.orm import Session
from app.models.problem_topic import ProblemTopic
from app.models.topic import Topic
from app.repositories.base import BaseRepository


class TopicRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, topic: Topic) -> Topic:
        self.db.add(topic)
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def get_by_id(self, topic_id: int) -> Topic | None:
        return (
            self.db.query(Topic)
            .filter(Topic.id == topic_id)
            .first()
        )

    def get_by_name(self, name: str) -> Topic | None:
        return (
            self.db.query(Topic)
            .filter(Topic.name == name)
            .first()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Topic]:
        return (
            self.db.query(Topic)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, topic: Topic) -> Topic:
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def delete(self, topic: Topic) -> None:
        self.db.delete(topic)
        self.db.commit()

    def exists(self, topic_id: int) -> bool:
        return (
            self.db.query(Topic)
            .filter(Topic.id == topic_id)
            .first()
            is not None
        )

    def problem_has_topics(self, problem_id: int) -> bool:
        """Check if a problem already has topic relationships."""
        return (
            self.db.query(ProblemTopic)
            .filter(ProblemTopic.problem_id == problem_id)
            .first()
            is not None
        )