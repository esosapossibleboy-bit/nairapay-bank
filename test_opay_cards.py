import sqlite3
from opay_cards import (
    create_virtual_card,
    fund_virtual_card,
    list_user_cards,
    reveal_card_secrets,
    toggle_card_freeze,
)
from opay_db import create_bank_account, deposit_funds, get_wallet_dashboard, init_opay_db

def test_virtual_cards_funding_freeze_and_pin_reveal():
    conn = sqlite3.connect(":memory:")
    init_opay_db(conn)

    user = create_bank_account(conn, "Esosa Edoleyi", "esosa@bank.ng", "Password123!", "1234")
    uid = user["user_id"]
    deposit_funds(conn, uid, 50000.00)

    # 1. Create a Visa Dollar virtual card and fund it with N16,000 ($10.00)
    card = create_virtual_card(conn, uid, "USD")
    assert card["brand"] == "Visa Dollar"
    fund_res = fund_virtual_card(conn, uid, card["id"], 16000.00)
    assert fund_res["ok"] is True

    (first_card,) = list_user_cards(conn, uid)
    assert first_card["balance"] == 10.00
    assert get_wallet_dashboard(conn, uid)["balance_naira"] == 34000.00

    # 2. Freezing the card blocks funding until unfrozen
    assert toggle_card_freeze(conn, uid, card["id"]) is True
    assert fund_virtual_card(conn, uid, card["id"], 1600.00)["ok"] is False
    assert toggle_card_freeze(conn, uid, card["id"]) is False

    # 3. Wrong PIN blocks CVV/number reveal; valid PIN reveals full card details
    assert reveal_card_secrets(conn, uid, card["id"], "0000")["ok"] is False
    secrets = reveal_card_secrets(conn, uid, card["id"], "1234")
    assert secrets["ok"] is True
    assert len(secrets["cvv"]) == 3
    conn.close()
