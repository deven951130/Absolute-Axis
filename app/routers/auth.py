from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models import LoginRequest
from app.utils import verify_password, create_access_token, log_event, get_password_hash
from app.database import get_db, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        try:
            log_event(req.username or "Unknown", "SECURITY: Authentication Failure.")
        except: pass
        raise HTTPException(status_code=401, detail="Unauthorized")
    
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
