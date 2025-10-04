from sqlalchemy import Column, String, DECIMAL, TIMESTAMP, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import enum


class TransactionType(str, enum.Enum):
    FUND = "FUND"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


class TransactionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(String(36), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(DECIMAL(19, 4), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    status = Column(Enum(TransactionStatus), nullable=False, default=TransactionStatus.COMPLETED)

    # For transfers, store the other wallet's ID
    related_wallet_id = Column(String(36), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    wallet = relationship("Wallet", back_populates="transactions")

    def __repr__(self):
        return f"<WalletTransaction(id={self.id}, type={self.type}, amount={self.amount})>"