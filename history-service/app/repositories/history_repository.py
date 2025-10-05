from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal


from app.models import TransactionEvent


class HistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_event(self, wallet_id: str, user_id: str, amount: Decimal, event_type: str, transaction_id: str, event_data: dict) -> TransactionEvent:
        event = TransactionEvent(
            wallet_id=wallet_id,
            user_id=user_id,
            amount=amount,
            event_type=event_type,
            transaction_id=transaction_id,
            event_data=event_data
        )
        self.db.add(event)
        self.db.flush()
        return event
    
    def event_exists(self, transaction_id: str) -> bool:
        return self.db.query(TransactionEvent).filter(
            TransactionEvent.transaction_id == transaction_id
        ).first() is not None
        
    def events_exist(self, transaction_ids: List[str]) -> bool:
        return self.db.query(TransactionEvent).filter(
            TransactionEvent.transaction_id.in_(transaction_ids)
        ).first() is not None
    
    def get_wallet_history(self, wallet_id: str, limit: int = 50, offset: int = 0) -> List[TransactionEvent]:
        return (
            self.db.query(TransactionEvent)
            .filter(TransactionEvent.wallet_id == wallet_id)
            .order_by(TransactionEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_user_activity(self, user_id: str, limit: int = 50, offset: int = 0) -> List[TransactionEvent]:
        return (
            self.db.query(TransactionEvent)
            .filter(TransactionEvent.user_id == user_id)
            .order_by(TransactionEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )