"""
HETU SafePlay - Full-stack application for secure storage of Finnish personal identity numbers.
"""

import os
import re
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import psycopg2

# --- Constants ---
HETU_REGEX = re.compile(r"^\d{6}[A+\-]\d{3}[A-Z0-9]$")
HETU_CHECKSUM_TABLE = "0123456789ABCDEFHJKLMNPRSTUVWXY"
HETU_MAX_LENGTH = 15

# CORS: tuotannossa vain frontend, kehityksessä localhost
CORS_ORIGINS = (
    ["https://leevinhetuntarkistuskone.fi", "https://www.leevinhetuntarkistuskone.fi"]
    if os.getenv("ENV") == "production"
    else ["http://localhost:8000", "http://127.0.0.1:8000"]
)

# --- App setup ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="HETU SafePlay")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic model ---
class HetuPayload(BaseModel):
    hetu: str

    @field_validator("hetu")
    @classmethod
    def validate_hetu(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("HETU is required")
        cleaned = v.strip().upper()
        if len(cleaned) > HETU_MAX_LENGTH:
            raise ValueError("HETU too long")
        if not HETU_REGEX.match(cleaned):
            raise ValueError("Invalid HETU format")
        # Checksum validation: DDMMYY + ZZZ (9 digits), century char excluded
        ddmmyy = cleaned[:6]
        zzz = cleaned[7:10]
        num_str = ddmmyy + zzz
        remainder = int(num_str) % 31
        expected_char = HETU_CHECKSUM_TABLE[remainder]
        actual_char = cleaned[10]
        if actual_char != expected_char:
            raise ValueError("Invalid HETU checksum")
        return cleaned


# --- Database ---
def get_db_connection():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


def init_db():
    """Create database table if it does not exist."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hetut (
                    id SERIAL PRIMARY KEY,
                    encrypted_hetu BYTEA NOT NULL
                )
                """
            )
        conn.commit()


# --- Fernet encryption ---
def get_fernet():
    key = os.getenv("SALAUSAVAIN")
    if not key:
        raise RuntimeError("SALAUSAVAIN environment variable is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


# --- Routes ---
@app.get("/")
async def root():
    """Serve the frontend index.html."""
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "HETU SafePlay API"}


@app.post("/api/hetu")
@limiter.limit("5/minute")
async def store_hetu(request: Request, payload: HetuPayload):
    """Store encrypted HETU in the database."""
    fernet = get_fernet()
    encrypted = fernet.encrypt(payload.hetu.encode())
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO hetut (encrypted_hetu) VALUES (%s)",
                (encrypted,),
            )
        conn.commit()
    return {"status": "ok", "message": "Tallennettu"}


# --- Startup ---
@app.on_event("startup")
async def startup():
    try:
        init_db()
    except Exception:
        pass  # Allow app to start even if DB is not configured (e.g. for local dev)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        forwarded_allow_ips="*",
    )
