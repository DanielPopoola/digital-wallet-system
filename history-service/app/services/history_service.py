import logging
from sqlalchemy.orm import Session
from typing import List

from app.repositories import HistoryRepository
from app.schemas import (
    WalletEvent,
    WalletCreatedEvent,
    WalletFundedEvent,
    TransferCompletedEvent,
    TransferFailedEvent,
    TransactionEventResponse
)


logger = logging.getLogger(__name__)


class HistoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = HistoryRepository(db)

    def process_event(self, event: WalletEvent) -> bool:
        try:
            if isinstance(event, TransferCompletedEvent):
                if self.repository.events_exist([event.from_transaction_id, event.to_transaction_id]):
                    logger.info(
                        f"Transfer already processed: {event.from_transaction_id}, "
                        f"{event.to_transaction_id}"
                    )
                    return False
                
                # Create entry for sender (debit)
                self.repository.create_event(
                    wallet_id=event.from_wallet_id,
                    user_id=event.from_user_id,
                    amount=event.amount,
                    event_type=event.event_type.value,
                    transaction_id=event.from_transaction_id,
                    event_data=event.model_dump(mode='json')
                )

                # Create entry for receiver (credit)
                self.repository.create_event(
                    wallet_id=event.to_wallet_id,
                    user_id=event.to_user_id,
                    amount=event.amount,
                    event_type=event.event_type.value,
                    transaction_id=event.to_transaction_id,
                    event_data=event.model_dump(mode='json')
                )
                
                self.db.commit()
                logger.info(
                    f"Transfer processed: ${event.amount} from {event.from_wallet_id} "
                    f"to {event.to_wallet_id}"
                )
                return True

            elif isinstance(event, WalletFundedEvent):
                if self.repository.event_exists(event.transaction_id):
                    logger.info(f"Funding event already processed: {event.transaction_id}")
                    return False
                
                self.repository.create_event(
                    wallet_id=event.wallet_id,
                    user_id=event.user_id,
                    amount=event.amount,
                    event_type=event.event_type.value,
                    transaction_id=event.transaction_id,
                    event_data=event.model_dump(mode='json')
                )
                self.db.commit()
                logger.info(f"Wallet funded: {event.wallet_id}, amount: {event.amount}")
                return True
            
            elif isinstance(event, WalletCreatedEvent):
                if self.repository.event_exists(event.transaction_id):
                    logger.info(f"Creation event already processed: {event.transaction_id}")
                    return False
                
                self.repository.create_event(
                    wallet_id=event.wallet_id,
                    user_id=event.user_id,
                    amount=event.initial_balance,
                    event_type=event.event_type.value,
                    transaction_id=event.transaction_id,
                    event_data=event.model_dump(mode='json')
                )
                self.db.commit()
                logger.info(f"Wallet created: {event.wallet_id}")
                return True
            
            elif isinstance(event, TransferFailedEvent):
                # Store with synthetic ID
                synthetic_txn_id = event.transaction_id or f"failed-{event.timestamp.isoformat()}-{event.from_wallet_id}"
                
                if self.repository.event_exists(synthetic_txn_id):
                    logger.info(f"Failed transfer already logged: {synthetic_txn_id}")
                    return False
                
                self.repository.create_event(
                    wallet_id=event.from_wallet_id,
                    user_id=event.from_user_id,
                    amount=event.amount,
                    event_type=event.event_type.value,
                    transaction_id=synthetic_txn_id,
                    event_data=event.model_dump(mode='json')
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

    def get_wallet_history(
        self, 
        wallet_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> tuple[List[TransactionEventResponse], int]:
        events, total = self.repository.get_wallet_history(wallet_id, limit, offset)
        return [TransactionEventResponse.model_validate(event) for event in events], total
    
    def get_user_activity(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[TransactionEventResponse], int]:
        events, total = self.repository.get_user_activity(user_id, limit, offset)
        return [TransactionEventResponse.model_validate(event) for event in events], total