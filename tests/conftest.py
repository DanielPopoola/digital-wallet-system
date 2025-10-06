import pytest
import requests
import uuid
from typing import Dict
from decimal import Decimal


from tests.constants import WALLET_SERVICE_URL, HISTORY_SERVICE_URL
from tests.utils import create_test_wallet, fund_wallet, wait_for_history_events, wait_for_user_activity



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

        yield
        
    except requests.RequestException as e:
        pytest.fail(
            f"Services not running! Please start with docker-compose.\n"
            f"Error: {e}"
        )