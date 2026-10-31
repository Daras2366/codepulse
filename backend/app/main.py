from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analytics
from app.routers import dashboard
from app.routers import users
from app.routers import auth
from app.routers import achievements
from app.routers import contest_participations
from app.routers import contests
from app.routers import goals
from app.routers import platform_profiles
from app.routers import problem_router
from app.routers import rating_history
from app.routers import submissions
from app.routers import topics
from app.routers import sync
from app.routers import backfill
from app.routers import recommendations

import app.models

app = FastAPI(
    title="CodePulse API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router)
app.include_router(problem_router.router)
app.include_router(platform_profiles.router)
app.include_router(goals.router)
app.include_router(submissions.router)
app.include_router(contests.router)
app.include_router(contest_participations.router)
app.include_router(rating_history.router)
app.include_router(achievements.router)
app.include_router(topics.router)
app.include_router(sync.router)
app.include_router(backfill.router)
app.include_router(recommendations.router)

app.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"],
)

app.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

@app.get("/")
def root():
    return {
        "message": "Welcome to CodePulse API"
    }
    
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
