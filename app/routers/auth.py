from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models import LoginRequest
from app.utils import verify_password, create_access_token, log_event
from app.database import get_db, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        log_event(req.username or "Unknown", "SECURITY: Authentication Failure.")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = create_access_token(data={"sub": user.username})
    log_event(req.username, "Identity Verification: Session Established.")
    
    return {
        "token": token, 
        "username": user.username, 
        "role": user.role, 
        "avatar": user.avatar
    }
