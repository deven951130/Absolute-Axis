from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import shutil

from app.models import CreateUserRequest, AdminUserUpdate
from app.utils import get_current_user_obj, get_password_hash, log_event
from app.config import NAS_ROOT, QUOTA_PER_USER
from app.database import get_db, User

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/users")
def list_users(user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
    users = db.query(User).all()
    return [{"username": u.username, "role": u.role, "avatar": u.avatar} for u in users]

@router.post("/create_user")
def create_user(req: CreateUserRequest, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
        
    u = shutil.disk_usage(NAS_ROOT)
    if u.free < QUOTA_PER_USER: 
        raise HTTPException(status_code=400, detail="Insufficient HDD space for 1GB quota")
        
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user: 
        raise HTTPException(status_code=400, detail="User exists")
        
    new_user = User(
        username=req.username,
        password_hash=get_password_hash(req.password),
        role=req.role
    )
    db.add(new_user)
    db.commit()
    
    log_event(user["username"], f"Admin: Created user {req.username}")
    return {"status": "ok"}

@router.post("/update_user")
def admin_update_user(req: AdminUserUpdate, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
    
    target_user_obj = db.query(User).filter(User.username == req.target_user).first()
    if not target_user_obj:
        raise HTTPException(status_code=404)
    
    if req.new_pass:
        target_user_obj.password_hash = get_password_hash(req.new_pass)
    if req.new_role:
        target_user_obj.role = req.new_role
        
    db.commit()
    log_event(user["username"], f"Admin: Modified user {req.target_user}")
    return {"status": "ok"}
