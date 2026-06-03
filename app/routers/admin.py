from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import shutil
import os

from app.models import CreateUserRequest, AdminUserUpdate
from app.utils import get_current_user_obj, get_password_hash, log_event
from app.config import NAS_ROOT, QUOTA_PER_USER
from app.database import get_db, User, FileStar, FileShare

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/users")
def list_users(user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
    users = db.query(User).all()
    return [{"username": u.username, "role": u.role, "avatar": u.avatar, "quota_bytes": u.quota_bytes, "status": getattr(u, "status", "Approved")} for u in users]

@router.post("/create_user")
def create_user(req: CreateUserRequest, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
        
    u = shutil.disk_usage(NAS_ROOT)
    # Convert GB to Bytes
    requested_quota = req.quota_gb * 1073741824 if req.quota_gb else QUOTA_PER_USER
    
    if u.free < requested_quota: 
        raise HTTPException(status_code=400, detail="Insufficient HDD space for requested quota")
        
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user: 
        raise HTTPException(status_code=400, detail="User exists")
        
    new_user = User(
        username=req.username,
        password_hash=get_password_hash(req.password),
        role=req.role,
        quota_bytes=requested_quota,
        status="Approved"
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
    if req.quota_gb:
        target_user_obj.quota_bytes = req.quota_gb * 1073741824
    if req.status:
        target_user_obj.status = req.status
        
    db.commit()
    log_event(user["username"], f"Admin: Modified user {req.target_user}")
    return {"status": "ok"}

@router.delete("/users/{username}")
def delete_user(username: str, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403, detail="Permission denied")
        
    if username == user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account")
        
    target_user = db.query(User).filter(User.username == username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 1. 刪除關聯資料表資料
    db.query(FileStar).filter(FileStar.username == username).delete()
    db.query(FileShare).filter((FileShare.owner == username) | (FileShare.target == username)).delete()
    
    # 2. 刪除資料庫 User 紀錄
    db.delete(target_user)
    db.commit()
    
    # 3. 刪除實體 NAS 個人與垃圾桶目錄
    user_nas_path = os.path.join(NAS_ROOT, username)
    user_trash_path = os.path.join(NAS_ROOT, ".trash", username)
    
    if os.path.exists(user_nas_path):
        try:
            shutil.rmtree(user_nas_path)
        except Exception as e:
            print(f"Error removing user NAS path {user_nas_path}: {e}")
            
    if os.path.exists(user_trash_path):
        try:
            shutil.rmtree(user_trash_path)
        except Exception as e:
            print(f"Error removing user trash path {user_trash_path}: {e}")
            
    log_event(user["username"], f"Admin: Deleted user {username}")
    return {"status": "ok"}

