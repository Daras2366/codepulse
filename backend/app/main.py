from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import dashboard

from app.core.database import Base, engine 
import app.models

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CodePulse API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"],
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