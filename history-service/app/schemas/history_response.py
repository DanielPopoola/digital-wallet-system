from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import List, Any


class TransactionEventResponse(BaseModel):
    wallet_id: str
    user_id: str
    amount: Decimal
    event_type: str
    event_data: dict

    model_config = {
        "from_attributes": True
    }


class WalletHistoryResponse(BaseModel):
    wallet_id: str
    events: List[TransactionEventResponse]
    total: int
    limit: int
    offset: int


class UserActivityResponse(BaseModel):
    user_id: str
    events: List[TransactionEventResponse]
    total: int
    limit: int
    offset: int