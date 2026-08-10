from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.sync import SyncResult
from app.services.sync_service import (
    CodeforcesSyncError,
    CodeforcesSyncService,
    PlatformProfileNotFoundError,
    UnsupportedPlatformError,
)

router = APIRouter(
    prefix="/sync",
    tags=["Synchronization"],
)


@router.post(
    "/codeforces/{profile_id}",
    response_model=SyncResult,
)
def sync_codeforces(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    service = CodeforcesSyncService(db)

    try:
        return service.sync_codeforces_profile(profile_id)

    except PlatformProfileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except UnsupportedPlatformError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except CodeforcesSyncError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc