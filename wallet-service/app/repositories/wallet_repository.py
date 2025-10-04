from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from decimal import Decimal


from app.models import Wallet, WalletTransaction, TransactionType, TransactionStatus


class WalletRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_wallet(self, user_id: str, initial_balance: Decimal = Decimal('0')) -> Wallet:
        wallet = Wallet(
            user_id=user_id,
            balance=initial_balance,
            version=0
        )
        self.db.add(wallet)
        self.db.flush()
        return wallet

    def get_wallet_by_id(self, wallet_id: str) -> Optional[Wallet]:
        return self.db.query(Wallet).filter(Wallet.id == wallet_id).first()
    
    def get_wallets_by_user(self, user_id: str) -> List[Wallet]:
        return self.db.query(Wallet).filter(Wallet.user_id == user_id).all()

    def update_wallet_balance(self, wallet_id: str, new_balance: Decimal, expected_version: int):
        result = self.db.query(Wallet).filter(
            and_(
                Wallet.id == wallet_id,
                Wallet.version == expected_version
            )
        ).update(
            {
                "balance": new_balance,
                "version": Wallet.version + 1
            },
            synchronize_session=False
        )

        return result > 0  # Return number of rows updated
    
    def lock_wallets_for_update(self, wallet_ids: List[str]) -> List[Wallet]:
        # Sort ids to ensure consistent lock order
        sorted_ids = sorted(wallet_ids)

        wallets = (
            self.db.query(Wallet)
            .filter(Wallet.id.in_(sorted_ids))
            .order_by(Wallet.id)
            .with_for_update()
            .all()
        )

        return wallets
    
    # ==================== Transaction Operations ====================

    def create_transaction(self, 
                           wallet_id: str,
                           amount: Decimal,
                           transaction_type: TransactionType, 
                           status: TransactionStatus = TransactionStatus.COMPLETED,
                           related_wallet_id: Optional[str] = None) -> WalletTransaction:
        transaction = WalletTransaction(
            wallet_id=wallet_id,
            amount=amount,
            type=transaction_type,
            status=status,
            related_wallet_id=related_wallet_id,
        )
        self.db.add(transaction)
        self.db.flush()
        return transaction
    
    def get_wallet_transactions(self, wallet_id: str, limit: int = 10, offset: int = 0):
        return (
            self.db.query(WalletTransaction)
            .filter(WalletTransaction.wallet_id == wallet_id)
            .order_by(WalletTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )