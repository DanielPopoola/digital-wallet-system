from app.schemas import (
    CreateWalletRequest, 
    FundWalletRequest, 
    TransferRequest,
    WalletResponse,
    TransferResponse,
)
from app.services import WalletService
from typing import Annotated
from fastapi import APIRouter, Depends
from app.dependencies import get_wallet_service

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post("", response_model= WalletResponse)
async def create_wallet(
    request: CreateWalletRequest,
    service: Annotated[WalletService, Depends(get_wallet_service)]
):
    return await service.create_wallet(request)


@router.post("/{wallet_id}/fund", response_model = WalletResponse)
async def fund_wallet(
    wallet_id: str,
    request: FundWalletRequest,
    service: Annotated[WalletService, Depends(get_wallet_service)]
):
    return await service.fund_wallet(wallet_id, request)


@router.post("/{wallet_id}/transfer", response_model = TransferResponse)
async def transfer_funds(
    wallet_id: str,
    request: TransferRequest,
    service: Annotated[WalletService, Depends(get_wallet_service)]
):
    return await service.transfer_funds(wallet_id, request)

@router.get("/{wallet_id}", response_model = WalletResponse)
async def get_wallet(wallet_id: str, service: Annotated[WalletService, Depends(get_wallet_service)]):
    return service.get_wallet(wallet_id)