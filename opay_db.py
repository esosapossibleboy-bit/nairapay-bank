import hashlib
import hmac
import random
import secrets
from datetime import datetime

def hash_secret(value: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"

def verify_secret(value: str, stored_value: str) -> bool:
    if not stored_value or "$" not in stored_value:
        return False
    salt, _ = stored_value.split("$", 1)
    return hmac.compare_digest(hash_secret(value, salt), stored_value)

def generate_account_number(cursor) -> str:
    while True:
        acct = "90" + "".join(str(random.randint(0, 9)) for _ in range(8))
        cursor.execute("SELECT id FROM bank_users WHERE account_number = ?", (acct,))
        if not cursor.fetchone():
            return acct

def init_opay_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            pin_hash TEXT NOT NULL,
            balance_kobo INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            counterparty TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            amount_kobo INTEGER NOT NULL,
            narration TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()

def create_bank_account(conn, full_name: str, email: str, password: str, pin: str):
    cursor = conn.cursor()
    acct_num = generate_account_number(cursor)
    pw_hash = hash_secret(password)
    pin_hash = hash_secret(pin)
    try:
        cursor.execute(
            """
            INSERT INTO bank_users (full_name, email, account_number, password_hash, pin_hash, balance_kobo)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (full_name.strip(), email.lower().strip(), acct_num, pw_hash, pin_hash),
        )
        conn.commit()
        return {"user_id": cursor.lastrowid, "full_name": full_name.strip(), "account_number": acct_num}
    except Exception:
        if hasattr(conn, "rollback"):
            conn.rollback()
        return None

def authenticate_bank_user(conn, email: str, password: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, account_number, password_hash FROM bank_users WHERE email = ?",
        (email.lower().strip(),),
    )
    row = cursor.fetchone()
    if not row:
        return None
    user_id, full_name, acct_num, pw_hash = row
    if verify_secret(password, pw_hash):
        return {"user_id": user_id, "full_name": full_name, "account_number": acct_num}
    return None

def lookup_account_name(conn, account_number: str):
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, account_number FROM bank_users WHERE account_number = ?", (account_number.strip(),))
    row = cursor.fetchone()
    if not row:
        return None
    return {"full_name": row[0], "account_number": row[1]}

def deposit_funds(conn, user_id: int, amount_naira: float, source: str = "Card / Bank Top-Up", timestamp: str = None):
    amount_kobo = round(amount_naira * 100)
    if amount_kobo <= 0:
        raise ValueError("Deposit must be positive")
    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "OPAY-" + secrets.token_hex(5).upper()
    cursor = conn.cursor()
    cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo + ? WHERE id = ?", (amount_kobo, user_id))
    cursor.execute(
        """
        INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
        VALUES (?, ?, ?, 'CREDIT', ?, ?, ?)
        """,
        (ref, user_id, source, amount_kobo, "Wallet Top-Up", when),
    )
    conn.commit()
    return ref

def pay_bill(conn, user_id: int, service: str, target: str, amount_naira: float, pin: str, timestamp: str = None):
    amount_kobo = round(amount_naira * 100)
    if amount_kobo <= 0:
        return {"ok": False, "error": "Amount must be greater than zero"}
    cursor = conn.cursor()
    cursor.execute("SELECT pin_hash, balance_kobo FROM bank_users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return {"ok": False, "error": "Account not found"}
    pin_hash, balance_kobo = row
    if not verify_secret(pin, pin_hash):
        return {"ok": False, "error": "Incorrect 4-digit Transaction PIN"}
    if balance_kobo < amount_kobo:
        return {"ok": False, "error": "Insufficient wallet balance"}

    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "BILL-" + secrets.token_hex(5).upper()
    cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo - ? WHERE id = ?", (amount_kobo, user_id))
    cursor.execute(
        """
        INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
        VALUES (?, ?, ?, 'DEBIT', ?, ?, ?)
        """,
        (ref, user_id, f"{service.strip()} ({target.strip()})", amount_kobo, f"{service.strip()} Purchase", when),
    )
    conn.commit()
    return {"ok": True, "reference": ref, "amount_naira": amount_kobo / 100}

def transfer_p2p(conn, sender_id: int, recipient_acct: str, amount_naira: float, pin: str, narration: str = "Transfer", timestamp: str = None):
    amount_kobo = round(amount_naira * 100)
    if amount_kobo <= 0:
        return {"ok": False, "error": "Amount must be greater than zero"}

    cursor = conn.cursor()
    cursor.execute("SELECT full_name, account_number, pin_hash, balance_kobo FROM bank_users WHERE id = ?", (sender_id,))
    sender = cursor.fetchone()
    if not sender:
        return {"ok": False, "error": "Sender not found"}
    sender_name, sender_acct, pin_hash, sender_balance = sender

    if not verify_secret(pin, pin_hash):
        return {"ok": False, "error": "Incorrect 4-digit Transaction PIN"}
    if sender_acct == recipient_acct.strip():
        return {"ok": False, "error": "Cannot transfer to your own account"}
    if sender_balance < amount_kobo:
        return {"ok": False, "error": "Insufficient wallet balance"}

    cursor.execute("SELECT id, full_name FROM bank_users WHERE account_number = ?", (recipient_acct.strip(),))
    recipient = cursor.fetchone()
    if not recipient:
        return {"ok": False, "error": "Recipient 10-digit account not found"}
    recipient_id, recipient_name = recipient

    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "OPAY-" + secrets.token_hex(5).upper()
    note = narration.strip() or "P2P Transfer"

    try:
        cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo - ? WHERE id = ?", (amount_kobo, sender_id))
        cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo + ? WHERE id = ?", (amount_kobo, recipient_id))
        cursor.execute(
            """
            INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
            VALUES (?, ?, ?, 'DEBIT', ?, ?, ?)
            """,
            (ref, sender_id, f"{recipient_name} ({recipient_acct})", amount_kobo, note, when),
        )
        cursor.execute(
            """
            INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
            VALUES (?, ?, ?, 'CREDIT', ?, ?, ?)
            """,
            (ref, recipient_id, f"{sender_name} ({sender_acct})", amount_kobo, note, when),
        )
        conn.commit()
        return {"ok": True, "reference": ref, "recipient_name": recipient_name, "amount_naira": amount_kobo / 100}
    except Exception:
        if hasattr(conn, "rollback"):
            conn.rollback()
        return {"ok": False, "error": "Transfer failed safely; balance unchanged"}

def get_wallet_dashboard(conn, user_id: int):
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, account_number, balance_kobo FROM bank_users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        return None
    full_name, acct_num, balance_kobo = user_row

    cursor.execute(
        """
        SELECT reference, counterparty, entry_type, amount_kobo, narration, created_at
        FROM ledger_entries
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    )
    history = [
        {
            "reference": ref,
            "counterparty": cp,
            "type": etype,
            "amount_naira": amt_kobo / 100,
            "narration": narr,
            "created_at": created_at,
        }
        for ref, cp, etype, amt_kobo, narr, created_at in cursor.fetchall()
    ]
    return {
        "full_name": full_name,
        "account_number": acct_num,
        "balance_naira": balance_kobo / 100,
        "transactions": history,
    }
