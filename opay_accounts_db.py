import hashlib
import hmac
import random
import secrets

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

def change_transaction_pin(conn, user_id: int, account_password: str, new_pin: str):
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM bank_users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return {"ok": False, "error": "Account not found"}
    (pw_hash,) = row
    if not verify_secret(account_password, pw_hash):
        return {"ok": False, "error": "Incorrect account password"}

    new_pin_hash = hash_secret(new_pin)
    cursor.execute("UPDATE bank_users SET pin_hash = ? WHERE id = ?", (new_pin_hash, user_id))
    conn.commit()
    return {"ok": True}

def lookup_account_name(conn, account_number: str):
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, account_number FROM bank_users WHERE account_number = ?", (account_number.strip(),))
    row = cursor.fetchone()
    if not row:
        return None
    full_name, acct_num = row
    return {"full_name": full_name, "account_number": acct_num}
