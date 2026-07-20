# auth.py
# JWT Authentication + Company Workspace Isolation

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv
# ── Password utils ────────────────────────────────────────────
import hashlib

load_dotenv(override=True)

SECRET_KEY   = os.getenv("JWT_SECRET", "change-this-in-production-please")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24 * 7   # 7 days in minutes

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer      = HTTPBearer()


# ── Schemas ───────────────────────────────────────────────────

class CompanyRegister(BaseModel):
    company_name: str
    email: str
    password: str
    industry: str = ""
    website: str  = ""

class UserLogin(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    company_id: str
    company_name: str
    email: str

class CompanyInDB(BaseModel):
    company_id: str
    company_name: str
    email: str
    industry: str = ""
    website: str  = ""

def hash_password(password: str) -> str:
    # Convert password to fixed 32-byte hash
    sha256_password = hashlib.sha256(password.encode("utf-8")).digest()
    return pwd_context.hash(sha256_password)

def verify_password(plain: str, hashed: str) -> bool:
    sha256_password = hashlib.sha256(plain.encode("utf-8")).digest()
    return pwd_context.verify(sha256_password, hashed)

# ── JWT utils ─────────────────────────────────────────────────

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again.",
        )


# ── Dependency: get current company from JWT ──────────────────

async def get_current_company(
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
) -> CompanyInDB:
    token = credentials.credentials
    payload = decode_token(token)

    company_id   = payload.get("company_id")
    company_name = payload.get("company_name")
    email        = payload.get("email")

    if not company_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return CompanyInDB(
        company_id=company_id,
        company_name=company_name,
        email=email,
        industry=payload.get("industry", ""),
        website=payload.get("website", ""),
    )