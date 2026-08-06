from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats():
    return {
        "problemsSolved": 342,
        "contestRating": 1820,
        "streak": 47,
        "acceptanceRate": 78.3
    }