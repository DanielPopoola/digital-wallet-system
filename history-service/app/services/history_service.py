import logging
from sqlalchemy.orm import Session
from typing import List

from app.repositories import HistoryRepository
from shared.schemas import (
    WalletEvent,
    WalletCreatedEvent,
    WalletFundedEvent,
    TransferCompletedEvent,
    TransferFailedEvent
)
from app.schemas import TransactionEventResponse

logger = logging.getLogger(__name__)


class HistoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = HistoryRepository(db)

    def _record_event(self, wallet_id, user_id, amount, event_type, transaction_id, event_data):
        self.repository.create_event(
            wallet_id=wallet_id,
            user_id=user_id,
            amount=amount,
            event_type=event_type,
            transaction_id=transaction_id,
            event_data=event_data,
        )

    def _exists(self, ids):
        if isinstance(ids, list):
            return self.repository.events_exist(ids)
        return self.repository.events_exist(ids)

    def process_event(self, event: WalletEvent) -> bool:
        try:
            if isinstance(event, TransferCompletedEvent):
                ids = [event.from_transaction_id, event.to_transaction_id]
                if self._exists(ids):
                    logger.info(f"Transfer already processed: {ids}")
                    return False
                
                self._record_event(
                    event.from_wallet_id, event.from_user_id, event.amount,
                    event.event_type.value, event.from_transaction_id,
                    event.model_dump(mode="json")
                )
                self._record_event(
                    event.to_wallet_id, event.to_user_id, event.amount,
                    event.event_type.value, event.to_transaction_id,
                    event.model_dump(mode="json")
                )
                self.db.commit()
                logger.info(
                    f"Transfer processed: ${event.amount} "
                    f"{event.from_wallet_id} → {event.to_wallet_id}"
                )
                return True
            
            if isinstance(event, (WalletFundedEvent, WalletCreatedEvent)):
                if self._exists(event.transaction_id):
                    logger.info(f"Event already processed: {event.transaction_id}")
                    return False

                amount = getattr(event, "amount", getattr(event, "initial_balance", 0))
                self._record_event(
                    event.wallet_id, event.user_id, amount,
                    event.event_type.value, event.transaction_id,
                    event.model_dump(mode="json")
                )
                self.db.commit()
                logger.info(f"{event.event_type.value} processed for wallet {event.wallet_id}")
                return True

            if isinstance(event, TransferFailedEvent):
                txn_id = event.transaction_id or f"failed-{event.timestamp.isoformat()}-{event.from_wallet_id}"
                if self._exists(txn_id):
                    logger.info(f"Failed transfer already logged: {txn_id}")
                    return False

                self._record_event(
                    event.from_wallet_id, event.from_user_id, event.amount,
                    event.event_type.value, txn_id,
                    event.model_dump(mode="json")
                )
                self.db.commit()
                logger.warning(
                    f"Transfer failed: {event.from_wallet_id} → {event.to_wallet_id}, "
                    f"reason: {event.reason}"
                )
                return True
            
            logger.warning(f"Unknown event type: {type(event)}")
            return False
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing event: {e}", exc_info=True)
            raise

    def get_wallet_history(self, wallet_id: str, limit: int = 50, offset: int = 0):
        events, total = self.repository.get_wallet_history(wallet_id, limit, offset)
        return [TransactionEventResponse.model_validate(e) for e in events], total

    def get_user_activity(self, user_id: str, limit: int = 50, offset: int = 0):
        events, total = self.repository.get_user_activity(user_id, limit, offset)
        return [TransactionEventResponse.model_validate(e) for e in events], total