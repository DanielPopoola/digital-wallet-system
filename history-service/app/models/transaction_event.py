from sqlalchemy import Column, String, DECIMAL, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base
import uuid


class TransactionEvent(Base):
    __tablename__ = "transaction_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(String(36), nullable=False)
    user_id = Column(String(100), nullable=False)
    amount = Column(DECIMAL(19,4), nullable=False)
    event_type = Column(String(30), nullable=False)
    transaction_id = Column(String(36), nullable=False,unique=True)
    event_data = Column(JSONB)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_transaction_event_wallet_id', 'wallet_id'),
        Index('idx_transaction_event_user_id', 'user_id'),
        Index('idx_transaction_event_transaction_id', 'transaction_id'),
    )


    def __repr__(self):
        return f"<TransactionEvents(id={self.id}, type={self.event_type}, amount={self.amount})>"