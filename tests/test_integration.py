import pytest
import requests
from decimal import Decimal


from tests.constants import WALLET_SERVICE_URL
from tests.utils import (
    create_test_wallet, 
    fund_wallet,
    get_wallet,
    transfer_funds,
    wait_for_history_events,
    wait_for_user_activity
)


@pytest.mark.integration
class TestBasicWalletFlow:

    def test_create_wallet_creates_history_event(self, unique_user_id):
        wallet = create_test_wallet(unique_user_id)
        wallet_id = wallet["id"]

        assert wallet["user_id"] == unique_user_id
        assert Decimal(wallet["balance"]) == Decimal("0")
        assert wallet["version"] == 0

        history = wait_for_history_events(wallet_id, expected_count=1, timeout=10)

        events = history["events"]
        assert len(events) == 1, "Should have exactly 1 event (WALLET_CREATED)"

        creation_event = events[0]
        assert creation_event["event_type"] == "WALLET_CREATED"
        assert creation_event["wallet_id"] == wallet_id
        assert creation_event["user_id"] == unique_user_id
        assert Decimal(creation_event["amount"]) == Decimal("0")

    def test_fund_wallet_updates_balance_and_history(self, test_wallet):
        wallet_id = test_wallet["id"]
        initial_balance = Decimal(test_wallet["balance"])
        fund_amount = Decimal("100.50")

        funded_wallet = fund_wallet(wallet_id, fund_amount)

        new_balance = Decimal(funded_wallet["balance"])
        expected_balance = initial_balance + fund_amount
        assert new_balance == expected_balance, f"Expected {expected_balance}, got {new_balance}"

        history = wait_for_history_events(wallet_id, expected_count=2, timeout=10)

        events = history["events"]
        assert len(events) == 2

        funding_event = events[0]
        creation_event = events[1]
        
        assert funding_event["event_type"] == "WALLET_FUNDED"
        assert Decimal(funding_event["amount"]) == fund_amount
        assert creation_event["event_type"] == "WALLET_CREATED"

    def test_multiple_funding_operations(self, test_wallet):
        wallet_id = test_wallet["id"]

        funding_amounts = [Decimal("50"), Decimal("30.25"), Decimal("19.75")]
        
        for amount in funding_amounts:
            fund_wallet(wallet_id, amount)

        wallet = get_wallet(wallet_id)
        excepted_total = sum(funding_amounts)
        assert Decimal(wallet["balance"]) == excepted_total

        history = wait_for_history_events(wallet_id, expected_count=4, timeout=15)

        events = history["events"]
        assert len(events) == 4

        funded_events = [e for e in events if e["event_type"] == "WALLET_FUNDED"]
        assert len(funded_events) == 3, "Should have 3 funding events"
        
        # Verify amounts (events are newest first)
        funded_amounts_in_history = [Decimal(e["amount"]) for e in funded_events]
        assert funded_amounts_in_history == list(reversed(funding_amounts))


@pytest.mark.integration
class TestTransferFlow:

    def test_transfer_updates_both_wallet_and_history(self, two_test_wallets):
        wallet_a, wallet_b = two_test_wallets
        wallet_a_id = wallet_a["id"]
        wallet_b_id = wallet_b["id"]

        wallet_a_initial = Decimal(get_wallet(wallet_a_id)["balance"])
        wallet_b_initial = Decimal(get_wallet(wallet_b_id)["balance"])

        transfer_amount = Decimal("50.00")

        transfer_result = transfer_funds(wallet_a_id, wallet_b_id, transfer_amount)

        assert transfer_result["from_wallet_id"] == wallet_a_id
        assert transfer_result["to_wallet_id"] == wallet_b_id
        assert Decimal(transfer_result["amount"]) == transfer_amount

        wallet_a_after = get_wallet(wallet_a_id)
        wallet_b_after = get_wallet(wallet_b_id)
        
        assert Decimal(wallet_a_after["balance"]) == wallet_a_initial - transfer_amount
        assert Decimal(wallet_b_after["balance"]) == wallet_b_initial + transfer_amount

        # wallet_a had: 1 creation + 1 funding + 1 transfer_out = 3 events
        history_a = wait_for_history_events(wallet_a_id, expected_count=3, timeout=10)

        transfer_event_a = history_a["events"][0]  # Most recent
        assert transfer_event_a["event_type"] == "TRANSFER_COMPLETED"
        assert Decimal(transfer_event_a["amount"]) == transfer_amount
        
        # wallet_b had: 1 creation + 1 transfer_in = 2 events
        history_b = wait_for_history_events(wallet_b_id, expected_count=2, timeout=10)
        
        transfer_event_b = history_b["events"][0]
        assert transfer_event_b["event_type"] == "TRANSFER_COMPLETED"
        assert Decimal(transfer_event_b["amount"]) == transfer_amount


    def test_transfer_insufficient_balance_fails(self, two_test_wallets):
        wallet_a, wallet_b = two_test_wallets
        wallet_a_id = wallet_a["id"]
        wallet_b_id = wallet_b["id"]

        insufficent_amount = Decimal("150.00")

        wallet_a_initial = get_wallet(wallet_a_id)
        wallet_b_initial = get_wallet(wallet_b_id)

        response = requests.post(
            f"{WALLET_SERVICE_URL}/wallets/{wallet_a_id}/transfer",
            json={
                "to_wallet_id": wallet_b_id,
                "amount": str(insufficent_amount)
            }
        )

        assert response.status_code == 400, "Should return 400 Bad Request"
        assert "insufficient" in response.json()["detail"].lower()
        
        wallet_a_after = get_wallet(wallet_a_id)
        wallet_b_after = get_wallet(wallet_b_id)
        
        assert wallet_a_after["balance"] == wallet_a_initial["balance"]
        assert wallet_b_after["balance"] == wallet_b_initial["balance"]

        history_a = wait_for_history_events(wallet_a_id, expected_count=2, timeout=10)

        transfer_event_a = history_a["events"][0]
        assert transfer_event_a["event_type"] == "TRANSFER_FAILED"

    
@pytest.mark.integration
class TestUserActivityTracking:

    def test_user_activity_show_all_wallet_operations(self, unique_user_id):
        wallet_1 = create_test_wallet(unique_user_id)
        wallet_2 = create_test_wallet(unique_user_id)

        fund_wallet(wallet_1["id"], Decimal("100.00"))
        fund_wallet(wallet_2["id"], Decimal("50.00"))

        transfer_funds(wallet_1["id"], wallet_2["id"], Decimal("25"))

        # Expected events:
        # - 2 wallet creations
        # - 2 fundings
        # - 2 transfer events (one for sender, one for receiver)
        # Total: 6 events

        activity = wait_for_user_activity(unique_user_id, expected_count=6, timeout=15)
        
        events = activity["events"]
        assert len(events) >= 6, f"Expected at least 6 events, got {len(events)}"

        event_types = [e["event_type"] for e in events]
        created_count = event_types.count("WALLET_CREATED")
        funded_count = event_types.count("WALLET_FUNDED")
        transfer_count = event_types.count("TRANSFER_COMPLETED")

        assert created_count == 2, "Should have 2 wallet creations"
        assert funded_count == 2, "Should have 2 funding events"
        assert transfer_count == 2, "Should have 2 transfer events (sender + receiver)"

        wallet_ids_in_activity = set(e["wallet_id"] for e in events)
        assert wallet_1["id"] in wallet_ids_in_activity
        assert wallet_2["id"] in wallet_ids_in_activity


@pytest.mark.integration
class TestDataConsistency:

    def test_wallet_balance_matches_history_sum(self, test_wallet):
        wallet_id = test_wallet["id"]

        operations = [
            ("fund", Decimal("100")),
            ("fund", Decimal("50.25")),
            ("fund", Decimal("30.75")),
        ]
        
        for op_type, amount in operations:
            if op_type == "fund":
                fund_wallet(wallet_id, amount)

        wallet = get_wallet(wallet_id)
        actual_balance = Decimal(wallet["balance"])

        history = wait_for_history_events(
            wallet_id,
            expected_count=len(operations) + 1,  # +1 for creation
            timeout=15)

        events = history["events"]

        reconstructed_balance = sum(
            Decimal(e["amount"]) 
            for e in events 
            if e["event_type"] == "WALLET_FUNDED"
        )

        assert actual_balance == reconstructed_balance, (
            f"Balance mismatch! "
            f"Wallet Service: {actual_balance}, "
            f"History reconstruction: ${reconstructed_balance}"
        )