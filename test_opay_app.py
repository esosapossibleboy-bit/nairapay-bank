import os
from fastapi.testclient import TestClient
import opay_server
from rate_limiter import RateLimiter

client = TestClient(opay_server.app)

def test_full_nairapay_banking_flow(monkeypatch):
    test_db = "temp_nairapay.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    monkeypatch.setattr(opay_server, "BANK_DB", test_db)
    monkeypatch.setattr(opay_server, "tx_limiter", RateLimiter(max_requests=20))

    # 1. Open two microfinance accounts with 10-digit account numbers and 4-digit PINs
    esosa = client.post("/auth/register", json={"full_name": "Esosa Edoleyi", "email": "esosa@bank.ng", "password": "Password123!", "pin": "1234"}).json()
    tunde = client.post("/auth/register", json={"full_name": "Tunde Bakare", "email": "tunde@bank.ng", "password": "Password123!", "pin": "5678"}).json()
    esosa_h = {"Authorization": f"Bearer {esosa['token']}"}
    tunde_h = {"Authorization": f"Bearer {tunde['token']}"}

    # 2. Verify recipient lookup & PIN-protected top-up of N50,000
    lookup = client.get(f"/wallet/lookup/{tunde['account_number']}", headers=esosa_h).json()
    assert lookup["full_name"] == "Tunde Bakare"

    assert client.post("/wallet/deposit", headers=esosa_h, json={"amount": 50000, "pin": "0000"}).status_code == 400
    topup = client.post("/wallet/deposit", headers=esosa_h, json={"amount": 50000, "pin": "1234"}).json()
    assert topup["balance_naira"] == 50000.0

    # 3. Wrong PIN is blocked; valid P2P transfer of N15,000 succeeds atomically
    bad = client.post("/wallet/transfer", headers=esosa_h, json={"recipient_account": tunde["account_number"], "amount": 15000, "pin": "0000"})
    assert bad.status_code == 400

    ok = client.post("/wallet/transfer", headers=esosa_h, json={"recipient_account": tunde["account_number"], "amount": 15000, "pin": "1234", "narration": "Laptop"})
    assert ok.status_code == 200
    assert ok.json()["dashboard"]["balance_naira"] == 35000.0
    assert client.get("/wallet", headers=tunde_h).json()["balance_naira"] == 15000.0

    # 4. Change PIN from 1234 to 4321 using account password, then pay N2,000 Airtime bill
    assert client.post("/auth/change-pin", headers=esosa_h, json={"password": "WrongPassword!", "new_pin": "4321"}).status_code == 400
    assert client.post("/auth/change-pin", headers=esosa_h, json={"password": "Password123!", "new_pin": "4321"}).status_code == 200

    bill = client.post("/wallet/bills", headers=esosa_h, json={"service": "MTN Airtime", "target": "08012345678", "amount": 2000, "pin": "4321"})
    assert bill.status_code == 200
    assert bill.json()["dashboard"]["balance_naira"] == 33000.0

    # 5. Download PDF statement
    pdf = client.get("/wallet/statement/pdf", headers=esosa_h)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    if os.path.exists(test_db):
        os.remove(test_db)
