from app.schemas import WalletHistoryResponse, UserActivityResponse
from app.services import HistoryService
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.dependencies import get_history_service


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/wallets/{wallet_id}", response_model=WalletHistoryResponse)
async def get_wallet_history(
    wallet_id: str,
    service: Annotated[HistoryService, Depends(get_history_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    events, total  = service.get_wallet_history(wallet_id, limit, offset)
    
    return WalletHistoryResponse(
        wallet_id=wallet_id,
        events=events,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/users/{user_id}", response_model=UserActivityResponse)
async def get_user_activity(
    user_id: str,
    service: Annotated[HistoryService, Depends(get_history_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    events, total = service.get_user_activity(user_id, limit, offset)
    
    return UserActivityResponse(
        user_id=user_id,
        events=events,
        total=total,
        limit=limit,
        offset=offset,
    )