import sqlite3
from opay_db import create_bank_account, deposit_funds, get_wallet_dashboard, init_opay_db
from opay_savings import credit_vault_interest, deposit_to_vault, get_vault_balance, withdraw_from_vault

def test_owealth_savings_vault_and_interest():
    conn = sqlite3.connect(":memory:")
    init_opay_db(conn)

    user = create_bank_account(conn, "Esosa Edoleyi", "esosa@bank.ng", "Password123!", "1234")
    uid = user["user_id"]
    deposit_funds(conn, uid, 100000.00)

    # 1. Move N40,000 from Main Wallet to OWealth Vault
    save_res = deposit_to_vault(conn, uid, 40000.00)
    assert save_res["ok"] is True
    assert get_vault_balance(conn, uid) == 40000.00
    assert get_wallet_dashboard(conn, uid)["balance_naira"] == 60000.00

    # 2. Earn 30-day interest at 15% p.a.
    int_res = credit_vault_interest(conn, uid, days=30)
    assert int_res["ok"] is True
    assert int_res["interest_naira"] > 490.0

    # 3. Wrong PIN blocks withdrawal; right PIN returns N10,000 to Main Wallet
    assert withdraw_from_vault(conn, uid, 10000.00, "0000")["ok"] is False
    wdr = withdraw_from_vault(conn, uid, 10000.00, "1234")
    assert wdr["ok"] is True
    assert get_wallet_dashboard(conn, uid)["balance_naira"] == 70000.00
    conn.close()
