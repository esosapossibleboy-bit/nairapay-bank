import re
import secrets
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field, field_validator
from db_adapter import get_db_connection
from opay_db import authenticate_bank_user, create_bank_account, init_opay_db
from rate_limiter import RateLimiter

auth_router = APIRouter()
ACTIVE_SESSIONS = {}
IDLE_TIMEOUT_SECONDS = 600
auth_limiter = RateLimiter(max_requests=20)

class BankRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=4, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    pin: str = Field(pattern=r"^\d{4}$")

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v) or not re.search(r"\d", v) or not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must include uppercase, lowercase, number, and symbol")
        return v

class BankLoginRequest(BaseModel):
    email: str = Field(min_length=4, max_length=120)
    password: str = Field(min_length=1, max_length=128)

def get_db():
    import opay_server
    return get_db_connection(opay_server.BANK_DB)

def create_bank_session(user_info: dict):
    token = secrets.token_urlsafe(32)
    ACTIVE_SESSIONS[token] = {
        "user_id": user_info["user_id"],
        "full_name": user_info["full_name"],
        "account_number": user_info["account_number"],
        "last_active": time.time(),
    }
    return {"token": token, **user_info}

def get_current_bank_user(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please log in first")
    _, token = authorization.split(" ", 1)
    session = ACTIVE_SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    now_ts = time.time()
    if now_ts - session["last_active"] > IDLE_TIMEOUT_SECONDS:
        ACTIVE_SESSIONS.pop(token, None)
        raise HTTPException(status_code=401, detail="Auto-locked due to inactivity.")
    session["last_active"] = now_ts
    return session

@auth_router.post("/auth/register")
def api_register(req: BankRegisterRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not auth_limiter.allow_request(ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    conn = get_db()
    init_opay_db(conn)
    created = create_bank_account(conn, req.full_name, req.email, req.password, req.pin)
    conn.close()
    if not created:
        raise HTTPException(status_code=400, detail="Email is already registered")
    return create_bank_session(created)

@auth_router.post("/auth/login")
def api_login(req: BankLoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not auth_limiter.allow_request(ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    conn = get_db()
    init_opay_db(conn)
    user = authenticate_bank_user(conn, req.email, req.password)
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return create_bank_session(user)

@auth_router.post("/auth/logout")
def api_logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        _, token = authorization.split(" ", 1)
        ACTIVE_SESSIONS.pop(token, None)
    return {"status": "logged_out"}
