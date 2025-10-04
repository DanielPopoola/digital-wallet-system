from app.schemas import WalletListResponse
from app.services import WalletService
from typing import Annotated
from fastapi import APIRouter, Depends
from app.dependencies import get_wallet_service


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}/wallets", response_model = WalletListResponse)
def get_user_wallets(user_id: str, service: Annotated[WalletService, Depends(get_wallet_service)]):
    wallets = service.get_user_wallets(user_id)
    return WalletListResponse(wallets=wallets, total=len(wallets))