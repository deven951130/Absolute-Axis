import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from app.models import LoginRequest
from app.utils import verify_password, create_access_token, log_event, get_password_hash
from app.database import get_db, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ----------------- 登入暴力破解防護 -----------------
# 同一個帳號或同一個來源 IP 在 15 分鐘內失敗 5 次，就鎖 5 分鐘（網站對外公開，一定要有）
_LOGIN_WINDOW_S = 15 * 60
_LOGIN_MAX_FAILS = 5
_LOGIN_LOCK_S = 5 * 60
_login_failures = defaultdict(list)


def _client_ip(request: Request) -> str:
    ip = request.client.host if request.client else "?"
    # 經 Cloudflare Tunnel 進來時，連線來源是本機的 cloudflared；只有這種情況才相信 CF-Connecting-IP
    if ip in ("127.0.0.1", "::1"):
        ip = request.headers.get("cf-connecting-ip", ip)
    return ip


def _login_keys(username: str, request: Request):
    return (f"user:{(username or '').strip().lower()}", f"ip:{_client_ip(request)}")


def _login_locked(keys, now: float) -> bool:
    for key in keys:
        recent = [t for t in _login_failures[key] if now - t < _LOGIN_WINDOW_S]
        _login_failures[key] = recent
        if len(recent) >= _LOGIN_MAX_FAILS and now - recent[-1] < _LOGIN_LOCK_S:
            return True
    return False


@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    keys = _login_keys(req.username, request)
    now = time.time()
    if _login_locked(keys, now):
        raise HTTPException(status_code=429, detail="登入失敗次數過多，請 5 分鐘後再試")

    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        for key in keys:
            _login_failures[key].append(now)
        try:
            log_event(req.username or "Unknown", "SECURITY: Authentication Failure.")
        except: pass
        raise HTTPException(status_code=401, detail="Unauthorized")
    for key in keys:
        _login_failures.pop(key, None)
    
    # 帳號審核狀態驗證
    if getattr(user, "status", "Approved") != "Approved":
        raise HTTPException(status_code=403, detail="帳號審核中或已被拒絕，請聯絡管理員")
    
    token = create_access_token(data={"sub": user.username})
    try:
        log_event(req.username, "Identity Verification: Session Established.")
    except: pass
    
    return {
        "token": token, 
        "username": user.username, 
        "role": user.role, 
        "avatar": user.avatar
    }

@router.post("/register")
def register(req: LoginRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="此帳號名稱已被註冊")
        
    new_user = User(
        username=req.username,
        password_hash=get_password_hash(req.password),
        role="Member",
        avatar="",
        status="Pending"
    )
    db.add(new_user)
    db.commit()
    
    try:
        log_event(req.username, "SECURITY: New account registered (Pending Approval).")
    except: pass
    
    return {"status": "ok", "message": "註冊成功，請等待管理員審核"}
