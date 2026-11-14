from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field
from db_adapter import get_db_connection
from opay_auth import get_current_bank_user
from opay_beneficiaries import list_beneficiaries
from opay_cards import (
    create_virtual_card,
    fund_virtual_card,
    list_user_cards,
    reveal_card_secrets,
    toggle_card_freeze,
)
from opay_db import get_wallet_dashboard, init_opay_db
from opay_pdf import build_bank_statement_pdf
from opay_savings import (
    credit_vault_interest,
    deposit_to_vault,
    get_vault_balance,
    withdraw_from_vault,
)

features_router = APIRouter()

class VaultSaveRequest(BaseModel):
    amount: float = Field(gt=0, le=50_000_000)
    pin: str = Field(pattern=r"^\d{4}$")
    timestamp: Optional[str] = Field(default=None, max_length=70)

class VaultWithdrawRequest(BaseModel):
    amount: float = Field(gt=0, le=50_000_000)
    pin: str = Field(pattern=r"^\d{4}$")
    timestamp: Optional[str] = Field(default=None, max_length=70)

class CardFundRequest(BaseModel):
    amount: float = Field(gt=0, le=50_000_000)
    timestamp: Optional[str] = Field(default=None, max_length=70)

class CardCreateRequest(BaseModel):
    currency: Literal["NGN", "USD"] = "NGN"

class CardPinRequest(BaseModel):
    pin: str = Field(pattern=r"^\d{4}$")

def get_db():
    import opay_server
    return get_db_connection(opay_server.BANK_DB)

def full_dashboard(conn, user_id: int) -> dict:
    dash = get_wallet_dashboard(conn, user_id)
    dash["vault_naira"] = get_vault_balance(conn, user_id)
    dash["beneficiaries"] = list_beneficiaries(conn, user_id)
    dash["cards"] = list_user_cards(conn, user_id)
    return dash

@features_router.post("/wallet/vault/save")
def api_vault_save(req: VaultSaveRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    result = deposit_to_vault(conn, user["user_id"], req.amount, req.timestamp, req.pin)
    if not result["ok"]:
        conn.close()
        raise HTTPException(status_code=400, detail=result["error"])
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return {"reference": result["reference"], "dashboard": dash}

@features_router.post("/wallet/vault/interest")
def api_vault_interest(req: CardPinRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    result = credit_vault_interest(conn, user["user_id"], days=30, pin=req.pin)
    if not result["ok"]:
        conn.close()
        raise HTTPException(status_code=400, detail=result["error"])
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return {"reference": result["reference"], "dashboard": dash}

@features_router.post("/wallet/vault/withdraw")
def api_vault_withdraw(req: VaultWithdrawRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    result = withdraw_from_vault(conn, user["user_id"], req.amount, req.pin, req.timestamp)
    if not result["ok"]:
        conn.close()
        raise HTTPException(status_code=400, detail=result["error"])
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return {"reference": result["reference"], "dashboard": dash}

@features_router.post("/wallet/cards")
def api_create_card(req: CardCreateRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    create_virtual_card(conn, user["user_id"], req.currency)
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return dash

@features_router.post("/wallet/cards/{card_id}/fund")
def api_fund_card(card_id: int, req: CardFundRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    result = fund_virtual_card(conn, user["user_id"], card_id, req.amount, req.timestamp)
    if not result["ok"]:
        conn.close()
        raise HTTPException(status_code=400, detail=result["error"])
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return {"reference": result["reference"], "dashboard": dash}

@features_router.post("/wallet/cards/{card_id}/freeze")
def api_freeze_card(card_id: int, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    state = toggle_card_freeze(conn, user["user_id"], card_id)
    if state is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Card not found")
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return dash

@features_router.post("/wallet/cards/{card_id}/reveal")
def api_reveal_card(card_id: int, req: CardPinRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    res = reveal_card_secrets(conn, user["user_id"], card_id, req.pin)
    conn.close()
    if not res["ok"]:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@features_router.get("/wallet/statement/pdf")
def api_statement_pdf(authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db()
    init_opay_db(conn)
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    pdf_bytes = build_bank_statement_pdf(dash)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="nairapay_statement.pdf"'},
    )
