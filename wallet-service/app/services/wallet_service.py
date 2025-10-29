import logging
from decimal import Decimal
from typing import List
from sqlalchemy.orm import Session

from app.repositories import WalletRepository
from shared.schemas.event_schema import (
    WalletCreatedEvent,
    WalletFundedEvent,
    TransferCompletedEvent,
    TransferFailedEvent,
)
from app.schemas import (
    CreateWalletRequest,
    FundWalletRequest,
    TransferRequest,
    WalletResponse,
    TransferResponse,
)
from app.models import TransactionType, TransactionStatus
from app.services.kafka_producer_service import kafka_producer
from app.services.utils import db_transaction, retry_optimistic_update, commit_and_refresh

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

   
    async def _publish_event(self, event):
        try:
            await kafka_producer.publish_event(event)
        except Exception as e:
            logger.error(f"Kafka publish failed: {e}")

    def _map_event(self, name: str, **kwargs):
        mapping = {
            "wallet_created": WalletCreatedEvent,
            "wallet_funded": WalletFundedEvent,
            "transfer_completed": TransferCompletedEvent,
            "transfer_failed": TransferFailedEvent,
        }
        return mapping[name](**kwargs)

    @db_transaction
    async def create_wallet(self, request: CreateWalletRequest) -> WalletResponse:
        wallet = self.repository.create_wallet(
            user_id=request.user_id,
            initial_balance=Decimal("0")
        )
        transaction = self.repository.create_transaction(
            wallet_id=wallet.id,
            amount=Decimal("0"),
            transaction_type=TransactionType.FUND,
            status=TransactionStatus.COMPLETED,
        )

        commit_and_refresh(self.db, wallet)
        logger.info(f"Wallet created: {wallet.id} for user {wallet.user_id}")

        event = self._map_event(
            "wallet_created",
            wallet_id=wallet.id,
            user_id=wallet.user_id,
            transaction_id=transaction.id,
            initial_balance=wallet.balance,
        )
        await self._publish_event(event)
        return WalletResponse.model_validate(wallet)

    @db_transaction
    async def fund_wallet(self, wallet_id: str, request: FundWalletRequest) -> WalletResponse:
        def attempt_update():
            wallet = self.repository.get_wallet_by_id(wallet_id)
            if not wallet:
                raise WalletNotFoundError(f"Wallet {wallet_id} not found")

            new_balance = wallet.balance + request.amount
            return self.repository.update_wallet_balance(
                wallet_id=wallet_id,
                new_balance=new_balance,
                expected_version=wallet.version,
            )

        retry_optimistic_update(wallet_id, attempt_update, self.db)

        transaction = self.repository.create_transaction(
            wallet_id=wallet_id,
            amount=request.amount,
            transaction_type=TransactionType.FUND,
            status=TransactionStatus.COMPLETED,
        )

        self.db.commit()
        wallet = self.repository.get_wallet_by_id(wallet_id)
        logger.info(f"Wallet {wallet_id} funded: ${request.amount}, new balance: ${wallet.balance}")

        event = self._map_event(
            "wallet_funded",
            wallet_id=wallet.id,
            user_id=wallet.user_id,
            transaction_id=transaction.id,
            amount=request.amount,
            new_balance=wallet.balance,
        )
        await self._publish_event(event)
        return WalletResponse.model_validate(wallet)

    @db_transaction
    async def transfer_funds(self, from_wallet_id: str, request: TransferRequest) -> TransferResponse:
        to_wallet_id = request.to_wallet_id
        wallets = self.repository.lock_wallets_for_update([from_wallet_id, to_wallet_id])

        from_wallet = next((w for w in wallets if w.id == from_wallet_id), None)
        to_wallet = next((w for w in wallets if w.id == to_wallet_id), None)

        if not from_wallet:
            raise WalletNotFoundError(f"Source wallet {from_wallet_id} not found")
        if not to_wallet:
            raise WalletNotFoundError(f"Destination wallet {to_wallet_id} not found")

        if from_wallet.balance < request.amount:
            event = self._map_event(
                "transfer_failed",
                from_wallet_id=from_wallet_id,
                from_user_id=from_wallet.user_id,
                to_wallet_id=to_wallet_id,
                amount=request.amount,
                reason="Insufficient balance",
            )
            await self._publish_event(event)
            raise InsufficientBalanceError(
                f"Insufficient balance: has ${from_wallet.balance}, needs ${request.amount}"
            )

        from_wallet.balance -= request.amount
        to_wallet.balance += request.amount
        from_wallet.version += 1
        to_wallet.version += 1

        debit_tx = self.repository.create_transaction(
            wallet_id=from_wallet_id,
            amount=request.amount,
            transaction_type=TransactionType.TRANSFER_OUT,
            status=TransactionStatus.COMPLETED,
            related_wallet_id=to_wallet_id,
        )
        credit_tx = self.repository.create_transaction(
            wallet_id=to_wallet_id,
            amount=request.amount,
            transaction_type=TransactionType.TRANSFER_IN,
            status=TransactionStatus.COMPLETED,
            related_wallet_id=from_wallet_id,
        )

        self.db.commit()
        logger.info(f"Transfer: ${request.amount} from {from_wallet_id} to {to_wallet_id}")

        event = self._map_event(
            "transfer_completed",
            from_wallet_id=from_wallet_id,
            to_wallet_id=to_wallet_id,
            from_user_id=from_wallet.user_id,
            to_user_id=to_wallet.user_id,
            amount=request.amount,
            from_transaction_id=debit_tx.id,
            to_transaction_id=credit_tx.id,
        )
        await self._publish_event(event)

        return TransferResponse(
            from_wallet_id=from_wallet_id,
            to_wallet_id=to_wallet_id,
            amount=request.amount,
        )

    def get_wallet(self, wallet_id: str) -> WalletResponse:
        wallet = self.repository.get_wallet_by_id(wallet_id)
        if not wallet:
            raise WalletNotFoundError(f"Wallet {wallet_id} not found")
        return WalletResponse.model_validate(wallet)

    def get_user_wallets(self, user_id: str) -> List[WalletResponse]:
        wallets = self.repository.get_wallets_by_user(user_id)
        return [WalletResponse.model_validate(w) for w in wallets]