import secrets
from datetime import datetime
from opay_db import verify_secret

ANNUAL_INTEREST_RATE = 0.15  # 15% per annum (OWealth-style)

def init_savings_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS savings_vaults (
            user_id INTEGER PRIMARY KEY,
            vault_kobo INTEGER DEFAULT 0
        )
    """)
    conn.commit()

def get_vault_balance(conn, user_id: int) -> float:
    init_savings_db(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT vault_kobo FROM savings_vaults WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return 0.0
    (vault_kobo,) = row
    return vault_kobo / 100

def deposit_to_vault(conn, user_id: int, amount_naira: float, timestamp: str = None, pin: str = None):
    init_savings_db(conn)
    amount_kobo = round(amount_naira * 100)
    if amount_kobo <= 0:
        return {"ok": False, "error": "Amount must be greater than zero"}

    cursor = conn.cursor()
    cursor.execute("SELECT balance_kobo, pin_hash FROM bank_users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        return {"ok": False, "error": "Account not found"}
    balance_kobo, pin_hash = user
    if pin is not None and not verify_secret(pin, pin_hash):
        return {"ok": False, "error": "Incorrect 4-digit Transaction PIN"}
    if balance_kobo < amount_kobo:
        return {"ok": False, "error": "Insufficient main wallet balance"}

    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "SAVE-" + secrets.token_hex(5).upper()

    cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo - ? WHERE id = ?", (amount_kobo, user_id))
    cursor.execute("SELECT vault_kobo FROM savings_vaults WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE savings_vaults SET vault_kobo = vault_kobo + ? WHERE user_id = ?", (amount_kobo, user_id))
    else:
        cursor.execute("INSERT INTO savings_vaults (user_id, vault_kobo) VALUES (?, ?)", (user_id, amount_kobo))

    cursor.execute(
        """
        INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
        VALUES (?, ?, 'OWealth Savings Vault', 'DEBIT', ?, 'Auto-Save to Vault', ?)
        """,
        (ref, user_id, amount_kobo, when),
    )
    conn.commit()
    return {"ok": True, "reference": ref, "vault_naira": get_vault_balance(conn, user_id)}

def credit_vault_interest(conn, user_id: int, days: int = 30, timestamp: str = None, pin: str = None):
    init_savings_db(conn)
    cursor = conn.cursor()
    if pin is not None:
        cursor.execute("SELECT pin_hash FROM bank_users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        if not u:
            return {"ok": False, "error": "Account not found"}
        (pin_hash,) = u
        if not verify_secret(pin, pin_hash):
            return {"ok": False, "error": "Incorrect 4-digit Transaction PIN"}

    cursor.execute("SELECT vault_kobo FROM savings_vaults WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return {"ok": False, "error": "No savings balance to earn interest"}
    (vault_kobo,) = row
    if vault_kobo <= 0:
        return {"ok": False, "error": "No savings balance to earn interest"}

    interest_kobo = round(vault_kobo * ANNUAL_INTEREST_RATE * (days / 365))
    if interest_kobo <= 0:
        interest_kobo = 1

    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "INT-" + secrets.token_hex(5).upper()
    cursor.execute("UPDATE savings_vaults SET vault_kobo = vault_kobo + ? WHERE user_id = ?", (interest_kobo, user_id))
    cursor.execute(
        """
        INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
        VALUES (?, ?, 'OWealth Interest (15% p.a.)', 'CREDIT', ?, ?, ?)
        """,
        (ref, user_id, interest_kobo, f"{days}-Day Savings Interest", when),
    )
    conn.commit()
    return {"ok": True, "reference": ref, "interest_naira": interest_kobo / 100, "vault_naira": get_vault_balance(conn, user_id)}

def withdraw_from_vault(conn, user_id: int, amount_naira: float, pin: str, timestamp: str = None):
    init_savings_db(conn)
    amount_kobo = round(amount_naira * 100)
    if amount_kobo <= 0:
        return {"ok": False, "error": "Amount must be greater than zero"}

    cursor = conn.cursor()
    cursor.execute("SELECT pin_hash FROM bank_users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        return {"ok": False, "error": "Account not found"}
    (pin_hash,) = user
    if not verify_secret(pin, pin_hash):
        return {"ok": False, "error": "Incorrect 4-digit Transaction PIN"}

    cursor.execute("SELECT vault_kobo FROM savings_vaults WHERE user_id = ?", (user_id,))
    vault = cursor.fetchone()
    if not vault:
        return {"ok": False, "error": "Insufficient OWealth vault balance"}
    (vault_kobo,) = vault
    if vault_kobo < amount_kobo:
        return {"ok": False, "error": "Insufficient OWealth vault balance"}

    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "WDR-" + secrets.token_hex(5).upper()
    cursor.execute("UPDATE savings_vaults SET vault_kobo = vault_kobo - ? WHERE user_id = ?", (amount_kobo, user_id))
    cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo + ? WHERE id = ?", (amount_kobo, user_id))
    cursor.execute(
        """
        INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
        VALUES (?, ?, 'OWealth Savings Vault', 'CREDIT', ?, 'Vault Withdrawal to Wallet', ?)
        """,
        (ref, user_id, amount_kobo, when),
    )
    conn.commit()
    return {"ok": True, "reference": ref, "vault_naira": get_vault_balance(conn, user_id)}
