from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def dashboard():
    return {
        "title": "Dashboard API"
    }