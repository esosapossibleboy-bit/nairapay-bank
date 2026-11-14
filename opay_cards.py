import random
import secrets
from datetime import datetime
from opay_db import verify_secret

USD_EXCHANGE_RATE = 1600.0  # 1 USD = 1,600 NGN (sandbox rate)

def init_cards_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS virtual_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            brand TEXT NOT NULL,
            currency TEXT NOT NULL,
            card_number TEXT UNIQUE NOT NULL,
            expiry TEXT NOT NULL,
            cvv TEXT NOT NULL,
            balance_cents INTEGER DEFAULT 0,
            is_frozen INTEGER DEFAULT 0
        )
    """)
    conn.commit()

def generate_card_number(cursor, prefix: str) -> str:
    while True:
        digits = prefix + "".join(str(random.randint(0, 9)) for _ in range(16 - len(prefix)))
        cursor.execute("SELECT id FROM virtual_cards WHERE card_number = ?", (digits,))
        if not cursor.fetchone():
            return digits

def create_virtual_card(conn, user_id: int, currency: str = "NGN"):
    init_cards_db(conn)
    cur = currency.upper().strip()
    brand = "Verve Naira" if cur == "NGN" else "Visa Dollar"
    prefix = "5061" if cur == "NGN" else "4532"
    cursor = conn.cursor()
    card_num = generate_card_number(cursor, prefix)
    cvv = "".join(str(random.randint(0, 9)) for _ in range(3))
    expiry = "11/29"
    cursor.execute(
        """
        INSERT INTO virtual_cards (user_id, brand, currency, card_number, expiry, cvv, balance_cents, is_frozen)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        """,
        (user_id, brand, cur, card_num, expiry, cvv),
    )
    conn.commit()
    return {"id": cursor.lastrowid, "brand": brand, "currency": cur, "last4": card_num[-4:]}

def list_user_cards(conn, user_id: int):
    init_cards_db(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, brand, currency, card_number, expiry, balance_cents, is_frozen
        FROM virtual_cards
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    )
    cards = []
    for cid, brand, cur, num, exp, bal_cents, frozen in cursor.fetchall():
        cards.append({
            "id": cid,
            "brand": brand,
            "currency": cur,
            "masked_number": f"{num[:4]} •••• •••• {num[-4:]}",
            "expiry": exp,
            "balance": bal_cents / 100,
            "is_frozen": bool(frozen),
        })
    return cards

def toggle_card_freeze(conn, user_id: int, card_id: int):
    init_cards_db(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT is_frozen FROM virtual_cards WHERE id = ? AND user_id = ?", (card_id, user_id))
    row = cursor.fetchone()
    if not row:
        return None
    (current_frozen,) = row
    new_state = 0 if current_frozen else 1
    cursor.execute("UPDATE virtual_cards SET is_frozen = ? WHERE id = ? AND user_id = ?", (new_state, card_id, user_id))
    conn.commit()
    return bool(new_state)

def reveal_card_secrets(conn, user_id: int, card_id: int, pin: str):
    init_cards_db(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT pin_hash FROM bank_users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        return {"ok": False, "error": "User not found"}
    (pin_hash,) = user
    if not verify_secret(pin, pin_hash):
        return {"ok": False, "error": "Incorrect 4-digit Transaction PIN"}

    cursor.execute("SELECT card_number, expiry, cvv FROM virtual_cards WHERE id = ? AND user_id = ?", (card_id, user_id))
    card = cursor.fetchone()
    if not card:
        return {"ok": False, "error": "Card not found"}
    num, exp, cvv = card
    formatted = " ".join(num[i:i+4] for i in range(0, 16, 4))
    return {"ok": True, "card_number": formatted, "expiry": exp, "cvv": cvv}

def fund_virtual_card(conn, user_id: int, card_id: int, amount_naira: float, timestamp: str = None):
    init_cards_db(conn)
    amount_kobo = round(amount_naira * 100)
    if amount_kobo <= 0:
        return {"ok": False, "error": "Amount must be greater than zero"}

    cursor = conn.cursor()
    cursor.execute("SELECT balance_kobo FROM bank_users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        return {"ok": False, "error": "User not found"}
    (balance_kobo,) = user
    if balance_kobo < amount_kobo:
        return {"ok": False, "error": "Insufficient main wallet balance"}

    cursor.execute("SELECT brand, currency, is_frozen FROM virtual_cards WHERE id = ? AND user_id = ?", (card_id, user_id))
    card = cursor.fetchone()
    if not card:
        return {"ok": False, "error": "Card not found"}
    brand, cur, frozen = card
    if frozen:
        return {"ok": False, "error": "Unfreeze card before funding"}

    credited_cents = amount_kobo if cur == "NGN" else round((amount_naira / USD_EXCHANGE_RATE) * 100)
    if credited_cents <= 0:
        return {"ok": False, "error": "Amount too small for USD conversion"}

    when = timestamp or datetime.now().strftime("%d %b %Y, %H:%M")
    ref = "CARD-" + secrets.token_hex(5).upper()
    cursor.execute("UPDATE bank_users SET balance_kobo = balance_kobo - ? WHERE id = ?", (amount_kobo, user_id))
    cursor.execute("UPDATE virtual_cards SET balance_cents = balance_cents + ? WHERE id = ?", (credited_cents, card_id))
    cursor.execute(
        """
        INSERT INTO ledger_entries (reference, user_id, counterparty, entry_type, amount_kobo, narration, created_at)
        VALUES (?, ?, ?, 'DEBIT', ?, ?, ?)
        """,
        (ref, user_id, f"{brand} Virtual Card", amount_kobo, f"Card Funding ({cur})", when),
    )
    conn.commit()
    return {"ok": True, "reference": ref}
