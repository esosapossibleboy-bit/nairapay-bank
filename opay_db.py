import secrets
from datetime import datetime
from opay_accounts_db import (
    authenticate_bank_user,
    change_transaction_pin,
    create_bank_account,
    generate_account_number,
    hash_secret,
    init_opay_db,
    lookup_account_name,
    verify_secret,
)

def deposit_funds(conn, user_id: int, amount_naira: float, source: str = "Card / Bank Top-Up", timestamp: str = None, pin: str = None):
    amount_kobo = round(amount_naira * 100)
    if amount_kobo <= 0:
        return {"ok": False, "error": "Deposit must be positive"}
    cursor = conn.cursor()
    if pin is not None:
        cursor.execute("SELECT pin_hash FROM bank_users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "error": "User not found"}
        (pin_hash,) = row
        if not verify_secret(pin, pin_hash):
            return {"ok": False, "error": "Incorrect 4-digit Transaction PIN"}

    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "OPAY-" + secrets.token_hex(5).upper()
    cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo + ? WHERE id = ?", (amount_kobo, user_id))
    cursor.execute(
        """
        INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
        VALUES (?, ?, ?, 'CREDIT', ?, ?, ?)
        """,
        (ref, user_id, source, amount_kobo, "Wallet Top-Up", when),
    )
    conn.commit()
    return {"ok": True, "reference": ref}

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
