from fastapi import APIRouter

from app.schemas.dashboard import DashboardStats
from app.services.dashboard_service import DashboardService

router = APIRouter()

service = DashboardService()

@router.get(
    "/stats",
    summary="Get dashboard statistics",
    description="Returns coding statistics for the logged-in user.",
    response_model=DashboardStats,
)
def get_dashboard_stats():
    return service.get_stats()