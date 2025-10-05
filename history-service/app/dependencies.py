from app.database import get_db
from app.services import HistoryService
from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import Depends


def get_history_service(
    db: Annotated[Session, Depends(get_db)]
) -> HistoryService:
    return HistoryService(db)