def init_beneficiaries_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beneficiaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            beneficiary_name TEXT NOT NULL,
            account_number TEXT NOT NULL,
            UNIQUE(user_id, account_number)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            idem_key TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            reference TEXT NOT NULL
        )
    """)
    conn.commit()

def save_beneficiary(conn, user_id: int, beneficiary_name: str, account_number: str):
    init_beneficiaries_db(conn)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO beneficiaries (user_id, beneficiary_name, account_number) VALUES (?, ?, ?)",
            (user_id, beneficiary_name.strip(), account_number.strip()),
        )
        conn.commit()
    except Exception:
        if hasattr(conn, "rollback"):
            conn.rollback()

def list_beneficiaries(conn, user_id: int):
    init_beneficiaries_db(conn)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT beneficiary_name, account_number FROM beneficiaries WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    )
    return [{"name": name, "account_number": acct} for name, acct in cursor.fetchall()]

def get_existing_transfer(conn, user_id: int, idem_key: str):
    if not idem_key:
        return None
    init_beneficiaries_db(conn)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT reference FROM idempotency_keys WHERE idem_key = ? AND user_id = ?",
        (idem_key, user_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None

def record_idempotency_key(conn, user_id: int, idem_key: str, reference: str):
    if not idem_key:
        return
    init_beneficiaries_db(conn)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO idempotency_keys (idem_key, user_id, reference) VALUES (?, ?, ?)",
            (idem_key, user_id, reference),
        )
        conn.commit()
    except Exception:
        if hasattr(conn, "rollback"):
            conn.rollback()
