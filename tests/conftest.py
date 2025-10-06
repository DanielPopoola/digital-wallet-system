import pytest
import requests
import time
import uuid
from typing import Dict, Optional
from decimal import Decimal


WALLET_SERVICE_URL = "http://localhost:8000"
HISTORY_SERVICE_URL = "http://localhost:8001"

# How long to wait for eventual consistency
DEFAULT_TIMEOUT = 10

# How often to check if history updated
POLL_INTERVAL = 0.5

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


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
            response = requests.get(f"{HISTORY_SERVICE_URL}/history/users/{user_id}")
            if response.status_code == 200:
                activity = response.json()
                events = activity.get("events", [])

                if len(events) >= expected_count:
                    return activity
                
            time.sleep(POLL_INTERVAL)

        except requests.RequestException as e:
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

# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture
def unique_user_id() -> str:
    return f"test-user-{uuid.uuid4()}"

@pytest.fixture
def test_wallet(unique_user_id) -> Dict:
    wallet = create_test_wallet(unique_user_id)

    wait_for_history_events(wallet["id"], expected_count=1)
    return wallet

@pytest.fixture
def two_test_wallets(unique_user_id: str) -> tuple[Dict, Dict]:
    wallet_a = create_test_wallet(unique_user_id)
    wallet_b = create_test_wallet(unique_user_id)
    
    fund_wallet(wallet_a["id"], Decimal("100"))
    
    wait_for_user_activity(unique_user_id, expected_count=3)
    
    return wallet_a, wallet_b

@pytest.fixture(scope="session")
def check_services_running():
    try:
        response = requests.get(f"{WALLET_SERVICE_URL}/", timeout=5)
        assert response.status_code == 200, "Wallet Service not responding"
        print("Wallet Service is running")
        
        response = requests.get(f"{HISTORY_SERVICE_URL}/", timeout=5)
        assert response.status_code == 200, "History Service not responding"
        print("History Service is running")
        
    except requests.RequestException as e:
        pytest.fail(
            f"Services not running! Please start with docker-compose.\n"
            f"Error: {e}"
        )


# ============================================================================
# PYTEST CONFIGURATION HOOKS
# ============================================================================

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "concurrent: marks tests that test concurrent operations"
    )
    config.addinivalue_line(
        "markers", "failure: marks tests that test failure scenarios"
    )


# Make check_services_running run automatically for all tests
@pytest.fixture(autouse=True, scope="session")
def setup_test_session(check_services_running):
    pass