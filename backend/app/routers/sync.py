from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.enums import Platform
from app.models.user import User
from app.schemas.sync import SyncResult
from app.services.base_sync_service import (
    PlatformProfileNotFoundError,
    ProfileAccessDeniedError,
    UnsupportedPlatformError,
)
from app.services.sync_service import (
    CodeforcesSyncError,
    CodeforcesSyncService,
    CodeforcesUsernameNotFoundError,
)
from app.services.leetcode_sync_service import (
    LeetCodeSyncError,
    LeetCodeSyncService,
    LeetCodeUsernameNotFoundError,
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

    except CodeforcesUsernameNotFoundError as exc:
        raise HTTPException(
            status_code=422,
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



@router.post(
    "/{platform}/{profile_id}",
    response_model=SyncResult,
)
def sync_platform_profile(
    platform: Platform,
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generic platform synchronization endpoint.
    
    Supports:
    - codeforces
    - leetcode
    - (future: codechef, atcoder)
    """
    
    # Route to appropriate service based on platform
    if platform == Platform.CODEFORCES:
        service = CodeforcesSyncService(db)
        try:
            return service.sync_codeforces_profile(profile_id, current_user.id)
        except CodeforcesUsernameNotFoundError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except CodeforcesSyncError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    
    elif platform == Platform.LEETCODE:
        service = LeetCodeSyncService(db)
        try:
            return service.sync_leetcode_profile(profile_id, current_user.id)
        except LeetCodeUsernameNotFoundError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LeetCodeSyncError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Platform {platform.value} is not supported yet.",
        )

    # Common error handling (caught by all platforms)
    try:
        pass  # Service calls are above
    except PlatformProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except UnsupportedPlatformError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{platform.value} synchronization failed due to malformed data.",
        ) from exc
