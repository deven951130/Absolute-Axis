import os
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.models import ProfileUpdate
from app.utils import get_current_user_obj, get_password_hash, log_event
from app.config import NAS_ROOT
from app.database import get_db, User

router = APIRouter(prefix="/api/user", tags=["user"])

@router.post("/update_profile")
def update_profile(req: ProfileUpdate, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    old_name = user["username"]
    user_obj = db.query(User).filter(User.username == old_name).first()
    
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")
        
    final_name = old_name
    
    # 更改使用者名稱
    if req.new_name and req.new_name != old_name:
        existing = db.query(User).filter(User.username == req.new_name).first()
        if existing:
            raise HTTPException(status_code=400, detail="新名稱已被使用")
            
        # 移動 NAS 目錄
        old_path = os.path.join(NAS_ROOT, old_name)
        new_path = os.path.join(NAS_ROOT, req.new_name)
        if os.path.exists(old_path): 
            os.rename(old_path, new_path)
            
        user_obj.username = req.new_name
        final_name = req.new_name
        log_event(old_name, f"Identity: Rename to {final_name}")

    if req.new_pass: 
        user_obj.password_hash = get_password_hash(req.new_pass)
        
    if req.avatar is not None: 
        user_obj.avatar = req.avatar
        
    db.commit()
    log_event(final_name, "Profile Update: Personal details modified.")
    return {"status": "ok", "new_username": final_name}
