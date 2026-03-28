import os
from fastapi import APIRouter, HTTPException, Depends

from app.models import ProfileUpdate
from app.utils import get_current_user_obj, read_db, write_db, hash_password, log_event
from app.config import NAS_ROOT

router = APIRouter(prefix="/api/user", tags=["user"])

@router.post("/update_profile")
def update_profile(req: ProfileUpdate, user: dict = Depends(get_current_user_obj)):
    db = read_db()
    old_name = user["username"]
    
    # 更改使用者名稱 (具備關鍵影響，需改 Key 並移動 NAS 目錄)
    final_name = old_name
    if req.new_name and req.new_name != old_name:
        if req.new_name in db: 
            raise HTTPException(status_code=400, detail="新名稱已被使用")
        
        db[req.new_name] = db.pop(old_name)
        # 移動 NAS 目錄
        old_path = os.path.join(NAS_ROOT, old_name)
        new_path = os.path.join(NAS_ROOT, req.new_name)
        if os.path.exists(old_path): 
            os.rename(old_path, new_path)
            
        final_name = str(req.new_name)
        log_event(old_name, f"Identity: Rename to {final_name}")

    if req.new_pass: 
        db[str(final_name)]["hash"] = hash_password(str(req.new_pass), db[str(final_name)]["salt"])
        
    if req.avatar is not None: 
        db[str(final_name)]["avatar"] = str(req.avatar)
        
    write_db(db)
    log_event(str(final_name), "Profile Update: Personal details modified.")
    return {"status": "ok", "new_username": final_name}
