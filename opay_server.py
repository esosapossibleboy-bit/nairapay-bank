from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from db_adapter import get_db_connection
from opay_auth import auth_router, get_current_bank_user
from opay_beneficiaries import (
    get_existing_transfer,
    record_idempotency_key,
    save_beneficiary,
)
from opay_db import (
    deposit_funds,
    init_opay_db,
    lookup_account_name,
    pay_bill,
    transfer_p2p,
)
from opay_features_router import features_router, full_dashboard
from opay_ui import render_opay_page
from rate_limiter import RateLimiter

app = FastAPI(title="NairaPay Microfinance Bank")
BANK_DB = "nairapay.db"
tx_limiter = RateLimiter(max_requests=40)
app.include_router(auth_router)
app.include_router(features_router)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

class DepositRequest(BaseModel):
    amount: float = Field(gt=0, le=50_000_000)
    pin: str = Field(pattern=r"^\d{4}$")
    timestamp: Optional[str] = Field(default=None, max_length=70)

class TransferRequest(BaseModel):
    recipient_account: str = Field(pattern=r"^\d{10}$")
    amount: float = Field(gt=0, le=10_000_000)
    pin: str = Field(pattern=r"^\d{4}$")
    narration: str = Field(default="Transfer", max_length=60)
    timestamp: Optional[str] = Field(default=None, max_length=70)
    idempotency_key: Optional[str] = Field(default=None, max_length=64)

class BillRequest(BaseModel):
    service: str = Field(min_length=2, max_length=40)
    target: str = Field(min_length=4, max_length=30)
    amount: float = Field(gt=0, le=1_000_000)
    pin: str = Field(pattern=r"^\d{4}$")
    timestamp: Optional[str] = Field(default=None, max_length=70)

@app.get("/", response_class=HTMLResponse)
def bank_home():
    return render_opay_page()

@app.get("/wallet")
def api_wallet(authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db_connection(BANK_DB)
    init_opay_db(conn)
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return dash

@app.get("/wallet/lookup/{account_number}")
def api_lookup(account_number: str, authorization: Optional[str] = Header(None)):
    get_current_bank_user(authorization)
    conn = get_db_connection(BANK_DB)
    init_opay_db(conn)
    info = lookup_account_name(conn, account_number)
    conn.close()
    if not info:
        raise HTTPException(status_code=404, detail="Account not found")
    return info

@app.post("/wallet/deposit")
def api_deposit(req: DepositRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db_connection(BANK_DB)
    init_opay_db(conn)
    res = deposit_funds(conn, user["user_id"], req.amount, "Instant Bank Top-Up", req.timestamp, req.pin)
    if not res["ok"]:
        conn.close()
        raise HTTPException(status_code=400, detail=res["error"])
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return dash

@app.post("/wallet/transfer")
def api_transfer(req: TransferRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    if not tx_limiter.allow_request(str(user["user_id"])):
        raise HTTPException(status_code=429, detail="Too many transfers. Slow down.")
    conn = get_db_connection(BANK_DB)
    init_opay_db(conn)

    existing_ref = get_existing_transfer(conn, user["user_id"], req.idempotency_key)
    if existing_ref:
        dash = full_dashboard(conn, user["user_id"])
        conn.close()
        return {"reference": existing_ref, "dashboard": dash}

    result = transfer_p2p(conn, user["user_id"], req.recipient_account, req.amount, req.pin, req.narration, req.timestamp)
    if not result["ok"]:
        conn.close()
        raise HTTPException(status_code=400, detail=result["error"])

    save_beneficiary(conn, user["user_id"], result["recipient_name"], req.recipient_account)
    record_idempotency_key(conn, user["user_id"], req.idempotency_key, result["reference"])
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return {"reference": result["reference"], "dashboard": dash}

@app.post("/wallet/bills")
def api_bills(req: BillRequest, authorization: Optional[str] = Header(None)):
    user = get_current_bank_user(authorization)
    conn = get_db_connection(BANK_DB)
    init_opay_db(conn)
    result = pay_bill(conn, user["user_id"], req.service, req.target, req.amount, req.pin, req.timestamp)
    if not result["ok"]:
        conn.close()
        raise HTTPException(status_code=400, detail=result["error"])
    dash = full_dashboard(conn, user["user_id"])
    conn.close()
    return {"reference": result["reference"], "dashboard": dash}
