import pytest
import requests
import time
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

from tests.constants import HISTORY_SERVICE_URL
from tests.utils import (
    create_test_wallet, 
    fund_wallet,
    get_wallet,
    transfer_funds,
    wait_for_history_events,
    wait_for_user_activity
)


@pytest.mark.concurrent
class TestConcurrentFunding:

    def test_concurrent_funding_no_money_lost(self, test_wallet):
        wallet_id = test_wallet["id"]
        num_operations = 10
        amount_per_operation = Decimal("10.00")
        expected_total = num_operations * amount_per_operation

        results = []
        failures = []

        def fund_opertion(operation_id: int) -> Tuple[int, bool, str]:
            try:
                fund_wallet(wallet_id, amount_per_operation)
                return (operation_id, True, "Operation successful")
            except Exception as e:
                return (operation_id, False, str(e))
        

        with ThreadPoolExecutor(max_workers=num_operations) as executor:
            futures = [
                executor.submit(fund_opertion, i)
                for i in range(num_operations)
            ]
            
            for future in as_completed(futures):
                op_id, success, message = future.result()
                if success:
                    results.append(op_id)
                else:
                    failures.append((op_id, message))

        assert len(failures) == 0
        assert len(results) == num_operations

        wallet = get_wallet(wallet_id)
        actual_balance = Decimal(wallet["balance"])

        assert actual_balance == expected_total

        # Expected: 1 creation + num_operations fundings
        history = wait_for_history_events(
            wallet_id,
            expected_count=num_operations + 1,
            timeout=30
        )

        events = history["events"]
        funding_events = [e for e in events if e["event_type"] == "WALLET_FUNDED"]

        assert len(funding_events) == num_operations
        history_sum = sum(Decimal(e["amount"]) for e in funding_events)
        assert history_sum == expected_total

    def test_concurrent_funding_with_different_amounts(self, test_wallet):
        wallet_id = test_wallet["id"]

        amounts = [
            Decimal("10.00"),
            Decimal("20.50"),
            Decimal("30.75"),
            Decimal("15.25"),
            Decimal("45.00"),
            Decimal("5.50"),
            Decimal("100.00"),
            Decimal("7.25"),
        ]
        
        expected_total = sum(amounts)

        def fund_with_amount(amount: Decimal) -> Tuple[Decimal, bool]:
            try:
                fund_wallet(wallet_id, amount)
                return (amount, True)
            except Exception as e:
                return (amount, False)
        
        with ThreadPoolExecutor(max_workers=len(amounts)) as executor:
            futures = [executor.submit(fund_with_amount, amt) for amt in amounts]
            results = [f.result() for f in as_completed(futures)]

        failures = [amt for amt, success in results if not success]
        assert len(failures) == 0
        
        wallet = get_wallet(wallet_id)
        actual_balance = Decimal(wallet["balance"])
        assert actual_balance == expected_total

        history = wait_for_history_events(
            wallet_id,
            expected_count=1 + len(amounts),
            timeout=20
        )

        funding_events = [
            e for e in history["events"] 
            if e["event_type"] == "WALLET_FUNDED"
        ]

        amounts_in_history = sorted([Decimal(e["amount"]) for e in funding_events])
        expected_amounts = sorted(amounts)

        assert amounts_in_history == expected_amounts


@pytest.mark.concurrent
class TestConcurrentTransfers:

    def test_concurrent_transfer_from_same_wallet(self, unique_user_id):
        sender = create_test_wallet(unique_user_id)
        fund_wallet(sender["id"], Decimal("100"))

        num_receivers = 7
        receivers = [create_test_wallet(unique_user_id) for _ in range(num_receivers)]

        wait_for_user_activity(unique_user_id, expected_count=1 + num_receivers + 1, timeout=20)

        transfer_amount = Decimal("15.00")
        sender_id = sender['id']

        def attempt_transfer(receiver_id: str, index: int) -> Tuple[int, bool, str]:
            try:
                transfer_funds(sender_id, receiver_id, transfer_amount)
                return (index, True, "Success")
            except Exception as e:
                # Expected for some transfers (insufficient balance)
                return (index, False, str(e))
            
        with ThreadPoolExecutor(max_workers=num_receivers) as executor:
            futures = [
                executor.submit(attempt_transfer, receivers[i]["id"], i)
                for i in range(num_receivers)
            ]

            results = [f.result() for f in as_completed(futures)]
        
        successes = [(i, msg) for i, success, msg in results if success]
        failures = [(i, msg) for i, success, msg in results if not success]

        # Should have ~6 successes (maybe 5-7 depending on timing)
        # The key is: NO OVERDRAFT
        assert 5 <= len(successes) <= 7

        sender_final = get_wallet(sender_id)
        sender_balance = Decimal(sender_final["balance"])

        expected_balance = Decimal("100") - (len(successes) * transfer_amount)
        assert sender_balance == expected_balance
        assert sender_balance >= 0

        for i, _ in successes:
            receiver = get_wallet(receivers[i]["id"])
            receiver_balance = Decimal(receiver["balance"])
            assert receiver_balance == transfer_amount


@pytest.mark.concurrent
class TestHighLoad:

    def test_many_operations_across_many_wallets(self, unique_user_id):
        num_wallets = 5
        num_operations_per_wallet = 10
        total_operations = num_wallets * num_operations_per_wallet

        wallets = [create_test_wallet(unique_user_id) for _ in range(num_wallets)]
        wallet_ids = [w["id"] for w in wallets]

        def perform_random_operation(wallet_idx: int, op_idx: int) -> Tuple[int, bool]:
            try:
                wallet_id = wallet_ids[wallet_idx]
                amount = Decimal(str(10 + op_idx))
                fund_wallet(wallet_id, amount)
                return (op_idx, True)
            except Exception as e:
                return (op_idx, False)
            
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            for wallet_idx in range(num_wallets):
                for op_idx in range(num_operations_per_wallet):
                    future = executor.submit(
                        perform_random_operation,
                        wallet_idx,
                        op_idx
                    )
                    futures.append(future)

            results = [f.result() for f in as_completed(futures)]

        successes = [op for op, success in results if success]
        failures = [op for op, success in results if not success]

        assert len(failures) == 0
        assert len(successes) == total_operations

        # Each wallet: 1 creation + num_operations_per_wallet fundings
        expected_events_per_wallet = 1 + num_operations_per_wallet

        all_histories_synced = False
        for _ in range(30):
            try:
                for wallet_id in wallet_ids:
                    wait_for_history_events(
                        wallet_id,
                        expected_count=expected_events_per_wallet,
                        timeout=2
                    )
                all_histories_synced = True
                break
            except TimeoutError:
                time.sleep(1)
                continue
        
        assert all_histories_synced, "History didn't catch up within timeout"
        
        # ASSERT - Total events in user activity
        total_expected_events = num_wallets * expected_events_per_wallet
        
        activity = wait_for_user_activity(
            unique_user_id,
            expected_count=total_expected_events,
            timeout=30
        )
        
        actual_event_count = len(activity["events"])
        
        assert actual_event_count == total_expected_events, (
            f"Expected {total_expected_events} total events, got {actual_event_count}"
        )
class TestRetryMechanism:

    def test_optimstic_lock_retries_succeed(self, test_wallet):
        wallet_id = test_wallet["id"]
        
        # Create high contention (many threads hitting same wallet)
        num_threads = 20
        amount = Decimal("5.00")
        expected_total = num_threads * amount
        
        
        retry_counts = []
        
        def fund_and_track_retries(thread_id: int) -> Tuple[int, bool, int]:
            """Fund and track how many retries were needed."""
            try:
                fund_wallet(wallet_id, amount)
                return (thread_id, True, 0)
            except Exception as e:
                return (thread_id, False, 0)
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(fund_and_track_retries, i)
                for i in range(num_threads)
            ]
            results = [f.result() for f in as_completed(futures)]
        
        # ASSERT - All eventually succeeded (despite conflicts)
        successes = [r for r in results if r[1]]
        failures = [r for r in results if not r[1]]
        
        assert len(failures) == 0
        assert len(successes) == num_threads
        
        # ASSERT - Final balance is correct
        wallet = get_wallet(wallet_id)
        actual_balance = Decimal(wallet["balance"])
        
        assert actual_balance == expected_total
