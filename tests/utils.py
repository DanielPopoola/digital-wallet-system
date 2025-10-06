import requests
import time
import uuid
from typing import Dict, Optional
from decimal import Decimal


from tests.constants import WALLET_SERVICE_URL, HISTORY_SERVICE_URL, DEFAULT_TIMEOUT, POLL_INTERVAL


def wait_for_history_events(wallet_id: str, expected_count: int, timeout: int = DEFAULT_TIMEOUT) -> Dict:
    start_time = time.time()

    while time.time() - start_time  < timeout:
        try:
            response = requests.get(f"{HISTORY_SERVICE_URL}/history/wallets/{wallet_id}")

            if response.status_code == 200:
                history = response.json()
                events = history.get('events', [])

                if len(events) >= expected_count:
                    print(f"Found {len(events)} events (expected {expected_count})")
                    return history
            
            # Not ready yet, wait and retry
            time.sleep(POLL_INTERVAL)

        except requests.RequestException as e:
            print(f"Error checking history: {e}")
            time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Timeout waiting for {expected_count} events in wallet {wallet_id}. "
        f"Check if History Service is running and consuming from Kafka."
    )

def wait_for_user_activity(user_id: str, expected_count: int, timeout: int = DEFAULT_TIMEOUT) -> Dict:
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{HISTORY_SERVICE_URL}/history/users/{user_id}",
                                    params={"limit":expected_count})
            if response.status_code == 200:
                activity = response.json()
                events = activity.get("events", [])

                if len(events) >= expected_count:
                    return activity
                
            time.sleep(POLL_INTERVAL)

        except requests.RequestException:
            time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Timeout waiting for {expected_count} events for user {user_id}"
    )

def create_test_wallet(user_id: Optional[str] = None) -> Dict:
    if user_id is None:
        user_id = f"test-user-{uuid.uuid4()}"

    response = requests.post(f"{WALLET_SERVICE_URL}/wallets", json={"user_id": user_id})

    assert response.status_code == 200, f"Failed to create wallet: {response.text}"
    
    wallet = response.json()
    print(f"Created test wallet: {wallet['id']} for user {user_id}")
    return wallet

def fund_wallet(wallet_id: str, amount: Decimal) -> Dict:
    response = requests.post(f"{WALLET_SERVICE_URL}/wallets/{wallet_id}/fund", json={"amount": str(amount)})
    assert response.status_code == 200, f"Failed to fund wallet: {response.text}"
    return response.json()

def transfer_funds(from_wallet_id: str, to_wallet_id: str, amount: Decimal) -> Dict:
    response = requests.post(
        f"{WALLET_SERVICE_URL}/wallets/{from_wallet_id}/transfer",
        json={
            "to_wallet_id": to_wallet_id,
            "amount": str(amount)
        }
    )
    assert response.status_code == 200, f"Failed to transfer: {response.text}"
    return response.json()

def get_wallet(wallet_id: str) -> Dict:
    response = requests.get(f"{WALLET_SERVICE_URL}/wallets/{wallet_id}")
    assert response.status_code == 200, f"Failed to get wallet: {response.text}"
    return response.json()
