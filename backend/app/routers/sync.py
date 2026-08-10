from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.sync import SyncResult
from app.services.sync_service import (
    CodeforcesSyncError,
    CodeforcesSyncService,
    PlatformProfileNotFoundError,
    ProfileAccessDeniedError,
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
    current_user: User = Depends(get_current_user),
):
    service = CodeforcesSyncService(db)

    try:
        return service.sync_codeforces_profile(
            profile_id,
            current_user.id,
        )

    except PlatformProfileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ProfileAccessDeniedError as exc:
        raise HTTPException(
            status_code=403,
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

    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Codeforces synchronization failed due to malformed data.",
        ) from exc