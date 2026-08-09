from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.topic import TopicResponse
from app.services.topic_service import TopicService

router = APIRouter(prefix="/topics", tags=["Topics"])


@router.get("/", response_model=list[TopicResponse])
def get_topics(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)):
    return TopicService(db).get_topics(skip, limit)


@router.get("/{topic_id}", response_model=TopicResponse)
def get_topic(topic_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    topic = TopicService(db).get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return topic
