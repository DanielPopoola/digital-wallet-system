from sqlalchemy import Column, String, DECIMAL, BigInteger, TIMESTAMP, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False, index=True)
    balance = Column(DECIMAL(19, 4), nullable=False, default=0)
    version = Column(BigInteger, nullable=False, default=0)
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    transactions = relationship("WalletTransaction", back_populates="wallet", lazy="select")

    def __repr__(self):
        return f"<Wallet(id={self.id}, user_id={self.user_id}, balance={self.balance})>"