from pydantic import BaseModel

class DashboardStats(BaseModel):
    problemsSolved: int
    contestRating: int
    streak: int
    acceptanceRate: float