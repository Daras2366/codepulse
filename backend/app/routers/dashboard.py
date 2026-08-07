from fastapi import APIRouter

from app.schemas.dashboard import DashboardStats
from app.services.dashboard_service import DashboardService

router = APIRouter()

service = DashboardService()


@router.get("/stats", response_model=DashboardStats,)
def get_dashboard_stats():
    return service.get_stats()