from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    WALLET_CREATED = "WALLET_CREATED"
    WALLET_FUNDED = "WALLET_FUNDED"
    TRANSFER_COMPLETED = "TRANSFER_COMPLETED"
    TRANSFER_FAILED = "TRANSFER_FAILED"


class WalletEventBase(BaseModel):
    event_type: EventType
    wallet_id: str
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    transaction_id: str


class WalletCreatedEvent(WalletEventBase):
    event_type: EventType = EventType.WALLET_CREATED
    initial_balance: Decimal


class WalletFundedEvent(WalletEventBase):
    event_type: EventType = EventType.WALLET_FUNDED
    amount: Decimal
    new_balance: Decimal


class TransferCompletedEvent(WalletEventBase):
    event_type: EventType = EventType.TRANSFER_COMPLETED
    to_wallet_id: str
    to_user_id: str
    amount: Decimal
    to_transaction_id: str


class TransferFailedEvent(WalletEventBase):
    event_type: EventType = EventType.TRANSFER_FAILED
    to_wallet_id: str
    amount: Decimal
    reason: str


WalletEvent = WalletCreatedEvent | WalletFundedEvent | TransferCompletedEvent | TransferFailedEvent