from app.database import get_db
from app.services import WalletService
from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import Depends


def get_wallet_service(db: Annotated[Session, Depends(get_db)]) -> WalletService:
    return WalletService(db)