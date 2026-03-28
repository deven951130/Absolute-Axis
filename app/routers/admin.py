import os
import shutil
import secrets
from fastapi import APIRouter, HTTPException, Depends

from app.models import CreateUserRequest, ProfileUpdate, AdminUserUpdate
from app.utils import get_current_user_obj, read_db, write_db, hash_password, log_event
from app.config import NAS_ROOT, QUOTA_PER_USER

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/users")
def list_users(user: dict = Depends(get_current_user_obj)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
    db = read_db()
    return [{"username": k, "role": v["role"], "avatar": v.get("avatar","")} for k, v in db.items()]

@router.post("/create_user")
def create_user(req: CreateUserRequest, user: dict = Depends(get_current_user_obj)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
        
    u = shutil.disk_usage(NAS_ROOT)
    if u.free < QUOTA_PER_USER: 
        raise HTTPException(status_code=400, detail="Insufficient HDD space for 1GB quota")
        
    db = read_db()
    if req.username in db: 
        raise HTTPException(status_code=400, detail="User exists")
        
    s = secrets.token_hex(16)
    db[req.username] = {
        "hash": hash_password(req.password, s), 
        "salt": s, 
        "role": req.role
    }
    
    write_db(db)
    log_event(user["username"], f"Admin: Created user {req.username}")
    return {"status": "ok"}

@router.post("/update_user")
def admin_update_user(req: AdminUserUpdate, user: dict = Depends(get_current_user_obj)):
    if user["role"] != "Administrator": 
        raise HTTPException(status_code=403)
    db = read_db()
    if req.target_user not in db: 
        raise HTTPException(status_code=404)
    
    if req.new_pass:
        db[req.target_user]["hash"] = hash_password(req.new_pass, db[req.target_user]["salt"])
    if req.new_role:
        db[req.target_user]["role"] = req.new_role
        
    write_db(db)
    log_event(user["username"], f"Admin: Modified user {req.target_user}")
    return {"status": "ok"}
