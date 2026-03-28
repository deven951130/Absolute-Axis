import secrets
from fastapi import APIRouter, HTTPException

from app.models import LoginRequest
from app.utils import read_db, hash_password, log_event
from app.config import ACTIVE_SESSIONS

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
def login(req: LoginRequest):
    db = read_db()
    u = db.get(req.username)
    if not u or hash_password(req.password, u["salt"]) != u["hash"]:
        log_event(req.username or "Unknown", "SECURITY: Authentication Failure.")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = secrets.token_hex(32)
    ACTIVE_SESSIONS[token] = req.username
    log_event(req.username, "Identity Verification: Session Established.")
    
    return {
        "token": token, 
        "username": req.username, 
        "role": u["role"], 
        "avatar": u.get("avatar", "")
    }
