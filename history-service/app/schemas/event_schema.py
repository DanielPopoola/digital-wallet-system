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


class TransferCompletedEvent(BaseModel):
    event_type: EventType = EventType.TRANSFER_COMPLETED
    from_wallet_id: str
    to_wallet_id: str
    from_user_id: str
    to_user_id: str
    amount: Decimal
    from_transaction_id: str
    to_transaction_id: str
    timestamp: datetime = Field(default_factory=datetime.now)

class TransferFailedEvent(BaseModel):
    event_type: EventType = EventType.TRANSFER_FAILED
    from_wallet_id: str
    from_user_id: str
    to_wallet_id: str
    amount: Decimal
    reason: str
    transaction_id: str
    timestamp: datetime = Field(default_factory=datetime.now)


WalletEvent = WalletCreatedEvent | WalletFundedEvent | TransferCompletedEvent | TransferFailedEvent