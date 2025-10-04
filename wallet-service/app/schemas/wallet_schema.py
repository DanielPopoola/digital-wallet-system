from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from enum import Enum
 

# Transaction states exposed in API
class TransactionTypeEnum(str, Enum):
    FUND = "FUND"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


class TransactionStatusEnum(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Request Schemas
class CreateWalletRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100, description="User ID who owns the wallet")
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_id cannot be empty or whitespace")
        return v.strip()


class AmountValidationMixin(BaseModel):
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v.quantize(Decimal("0.0001")) != v:
            raise ValueError("Amount cannot have more than 4 decimal places")
        return v


class FundWalletRequest(AmountValidationMixin):
    amount: Decimal = Field(..., gt=0, description="Amount to add (must be positive)")

class TransferRequest(AmountValidationMixin):
    to_wallet_id: str = Field(..., min_length=1, description="Recipient wallet ID")
    amount: Decimal = Field(..., gt=0, description="Amount to transfer (must be positive)")


# Response schema
class WalletResponse(BaseModel):
    id: str
    user_id: str
    balance: Decimal
    version: int

    model_config = {
        "from_attributes": True
    }

class TransactionResponse(BaseModel):
    id: str
    wallet_id: str
    amount: Decimal
    type: TransactionTypeEnum
    status: TransactionStatusEnum

    model_config = {
        "from_attributes": True
    }

class TransferResponse(BaseModel):
    from_wallet_id: str
    to_wallet_id: str
    amount: Decimal

class WalletListResponse(BaseModel):
    """Response containing list of wallets"""
    wallets: list[WalletResponse]
    total: int