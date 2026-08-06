from fastapi import FastAPI
from app.routers import dashboard

app = FastAPI(
    title="CodePulse API",
    version="1.0.0"
)

app.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"]
)


@app.get("/")
def root():
    return {
        "message": "Welcome to CodePulse API"
    }