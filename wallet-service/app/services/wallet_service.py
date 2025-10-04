import logging
from decimal import Decimal
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories import WalletRepository
from app.schemas import (
    CreateWalletRequest,
    FundWalletRequest,
    TransferRequest,
    WalletResponse,
    TransferResponse,
    WalletCreatedEvent,
    WalletFundedEvent,
    TransferCompletedEvent,
    TransferFailedEvent,
)
from app.models import TransactionType, TransactionStatus
from app.services.kafka_producer_service import kafka_producer

logger = logging.getLogger(__name__)


class InsufficientBalanceError(Exception):
    pass


class WalletNotFoundError(Exception):
    pass


class OptimisticLockError(Exception):
    pass


class WalletService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = WalletRepository(db)

    async def create_wallet(self, request: CreateWalletRequest) -> WalletResponse:
        try:
            wallet = self.repository.create_wallet(
                user_id=request.user_id,
                initial_balance=Decimal('0')
            )

            transaction = self.repository.create_transaction(
                wallet_id=wallet.id,
                amount=Decimal('0'),
                transaction_type=TransactionType.FUND,
                status=TransactionStatus.COMPLETED,
            )

            self.db.commit()
            self.db.refresh(wallet)
            logger.info(f"Wallet created: {wallet.id} for user {wallet.user_id}")

            event = WalletCreatedEvent(
                wallet_id=wallet.id,
                user_id=wallet.user_id,
                transaction_id=transaction.id,
                initial_balance=wallet.balance
            )
            await kafka_producer.publish_event(event)

            return WalletResponse.model_validate(wallet)
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Database integrity error creating wallet: {e}")
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating wallet: {e}")
            raise

    async def fund_wallet(self, wallet_id: str, request: FundWalletRequest) -> WalletResponse:
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                wallet = self.repository.get_wallet_by_id(wallet_id)
                if not wallet:
                    raise WalletNotFoundError(f"Wallet {wallet_id} not found")
                
                current_version = wallet.version
                new_balance = wallet.balance + request.amount

                success = self.repository.update_wallet_balance(
                    wallet_id=wallet_id,
                    new_balance=new_balance,
                    expected_version=current_version
                )

                if not success:
                    retry_count += 1
                    logger.warning(
                        f"Optimistic lock failed for wallet {wallet_id}, "
                        f"retry {retry_count}/{max_retries}"
                    )
                    self.db.rollback()
                    continue

                transaction = self.repository.create_transaction(
                    wallet_id=wallet_id,
                    amount=request.amount,
                    transaction_type=TransactionType.FUND,
                    status=TransactionStatus.COMPLETED,
                )

                self.db.commit()

                wallet = self.repository.get_wallet_by_id(wallet_id)
                logger.info(
                    f"Wallet {wallet_id} funded: ${request.amount}, "
                    f"new balance: ${wallet.balance}"
                )

                event = WalletFundedEvent(
                    wallet_id=wallet.id,
                    user_id=wallet.user_id,
                    transaction_id=transaction.id,
                    amount=request.amount,
                    new_balance=wallet.balance
                )
                await kafka_producer.publish_event(event)

                return WalletResponse.model_validate(wallet)
            
            except Exception as e:
                self.db.rollback()
                logger.error(f"Error funding wallet: {e}")
                
        raise OptimisticLockError(
            f"Failed to update wallet {wallet_id} after {max_retries} retries"
        )

    async def transfer_funds(self, from_wallet_id: str, request: TransferRequest) -> TransferResponse:
        to_wallet_id = request.to_wallet_id
        try:
            wallets = self.repository.lock_wallets_for_update([from_wallet_id, to_wallet_id])

            from_wallet = next((w for w in wallets if w.id == from_wallet_id), None)
            to_wallet = next((w for w in wallets if w.id == to_wallet_id), None)

            if not from_wallet:
                raise WalletNotFoundError(f"Source wallet {from_wallet_id} not found")
            if not to_wallet:
                raise WalletNotFoundError(f"Destination wallet {to_wallet_id} not found")
            
            # Check balance
            if from_wallet.balance < request.amount:
                event = TransferFailedEvent(
                    from_wallet_id=from_wallet_id,
                    to_wallet_id=to_wallet_id,
                    amount=request.amount,
                    reason="Insufficient balance"
                )
                await kafka_producer.publish_event(event)
                raise InsufficientBalanceError(
                    f"Insufficient balance: has ${from_wallet.balance}, needs ${request.amount}"
                )

            # Update balance
            from_wallet.balance -= request.amount
            from_wallet.version += 1
            to_wallet.balance += request.amount
            to_wallet.version += 1

            debit_transaction = self.repository.create_transaction(
                wallet_id=from_wallet_id,
                amount=request.amount,
                transaction_type=TransactionType.TRANSFER_OUT,
                status=TransactionStatus.COMPLETED,
                related_wallet_id=to_wallet_id
            )

            credit_transaction = self.repository.create_transaction(
                wallet_id=to_wallet_id,
                amount=request.amount,
                transaction_type=TransactionType.TRANSFER_IN,
                status=TransactionStatus.COMPLETED,
                related_wallet_id=from_wallet_id,
            )

            self.db.commit()

            logger.info(
                f"Transfer completed: ${request.amount} from {from_wallet_id} to {to_wallet_id}"
            )
            
            event = TransferCompletedEvent(
                from_wallet_id=from_wallet_id,
                to_wallet_id=to_wallet_id,
                from_user_id=from_wallet.user_id,
                to_user_id=to_wallet.user_id,
                amount=request.amount,
                from_transaction_id=debit_transaction.id,
                to_transaction_id=credit_transaction.id
            )
            await kafka_producer.publish_event(event)
            return TransferResponse(
                from_wallet_id=from_wallet_id,
                to_wallet_id=to_wallet_id,
                amount=request.amount
            )
        except (WalletNotFoundError, InsufficientBalanceError):
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error transferring funds: {e}")
            raise

    def get_wallet(self, wallet_id: str) -> WalletResponse:
        wallet = self.repository.get_wallet_by_id(wallet_id)
        if not wallet:
            raise WalletNotFoundError(f"Wallet {wallet_id} not found")
        
        return WalletResponse.model_validate(wallet)
    
    def get_user_wallets(self, user_id: str) -> List[WalletResponse]:
        wallets = self.repository.get_wallets_by_user(user_id)
        return [WalletResponse.model_validate(w) for w in wallets]
