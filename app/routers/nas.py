import os
import json
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.models import ItemRequest, ShareRequest, ToggleRequest
from app.utils import get_current_user_obj, safe_path, get_dir_size, log_event, read_db
from app.config import BASE_PATH, NAS_ROOT, QUOTA_PER_USER

router = APIRouter(prefix="/api/nas", tags=["nas"])

def load_meta():
    meta_path = os.path.join(BASE_PATH, "nas_meta.json")
    meta = {"starred": [], "shares": [], "trash": []}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f: 
            meta = json.load(f)
    return meta

def save_meta(meta):
    meta_path = os.path.join(BASE_PATH, "nas_meta.json")
    with open(meta_path, "w") as f: 
        json.dump(meta, f)


@router.get("/list")
def list_nas_files(path: str = "", mode: str = "drive", user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    items = []
    meta = load_meta()

    if mode == "drive":
        t = safe_path(path, u)
        if not os.path.exists(t): 
            return {"files": [], "quota_used": 0, "quota_total": QUOTA_PER_USER}
        
        for e in os.scandir(t):
            if e.name.startswith("."): 
                continue
            s = e.stat()
            full = (path.strip("/") + "/" + e.name).strip("/")
            items.append({
                "name": e.name, 
                "is_dir": e.is_dir(), 
                "size": s.st_size,
                "modified": datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "ext": os.path.splitext(e.name)[1].lower() if not e.is_dir() else "folder",
                "starred": any(x["user"] == u and x["path"] == full for x in meta["starred"]),
                "shared": any(x["owner"] == u and x["path"] == full for x in meta["shares"])
            })
            
    elif mode == "starred":
        for x in meta["starred"]:
            if x["user"] == u:
                p = safe_path(x["path"], u)
                if os.path.exists(p):
                    s = os.stat(p)
                    items.append({
                        "name": os.path.basename(p), "is_dir": os.path.isdir(p), 
                        "size": s.st_size, "modified": datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M"), 
                        "ext": os.path.splitext(p)[1].lower(), "path": x["path"], "starred": True
                    })
                    
    elif mode == "shared":
        for x in meta["shares"]:
            if x["target"] == u:
                p = safe_path(x["path"], x["owner"])
                if os.path.exists(p):
                    s = os.stat(p)
                    items.append({
                        "name": os.path.basename(p), "is_dir": os.path.isdir(p), 
                        "size": s.st_size, "modified": datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M"), 
                        "ext": os.path.splitext(p)[1].lower(), "path": x["path"], "owner": x["owner"]
                    })
                    
    elif mode == "trash":
        trash_dir = os.path.join(NAS_ROOT, ".trash", u)
        if os.path.exists(trash_dir):
            for e in os.scandir(trash_dir):
                s = e.stat()
                items.append({
                    "name": e.name, "is_dir": e.is_dir(), "size": s.st_size, 
                    "modified": datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M"), 
                    "ext": os.path.splitext(e.name)[1].lower()
                })
                
    elif mode == "recent":
        all_files = []
        user_root = safe_path("", u)
        for r, d, fs in os.walk(user_root):
            for f in fs:
                if f.startswith("."): 
                    continue
                p = os.path.join(r, f)
                s = os.stat(p)
                all_files.append({
                    "name": f, "is_dir": False, "size": s.st_size, 
                    "mtime": s.st_mtime, "path": os.path.relpath(p, user_root)
                })
        all_files.sort(key=lambda x: x["mtime"], reverse=True)
        items = [{
            "name": x["name"], "is_dir": x["is_dir"], "size": x["size"], 
            "modified": datetime.fromtimestamp(x["mtime"]).strftime("%Y-%m-%d %H:%M"), 
            "ext": os.path.splitext(x["name"])[1].lower(), "path": x["path"]
        } for x in all_files[:20]]

    user_root = safe_path("", u)
    return {
        "files": items if mode == "recent" else sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower())),
        "quota_used": get_dir_size(user_root), 
        "quota_total": QUOTA_PER_USER
    }


@router.post("/toggle_star")
def toggle_star(req: ToggleRequest, user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    meta = load_meta()
    
    idx = -1
    for i, x in enumerate(meta["starred"]):
        if x["user"] == u and x["path"] == req.path: 
            idx = i
            break
    
    if idx >= 0: 
        meta["starred"].pop(idx)
    else: 
        meta["starred"].append({"user": u, "path": req.path})
    
    save_meta(meta)
    return {"status": "ok"}


@router.get("/users")
def list_share_users(user: dict = Depends(get_current_user_obj)):
    db = read_db()
    return [{"username": k, "avatar": v.get("avatar","")} for k, v in db.items() if k != user["username"]]


@router.post("/share")
def share_file(req: ShareRequest, user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    meta = load_meta()
    meta["shares"].append({"owner": u, "path": req.path, "target": req.target_user})
    save_meta(meta)
    return {"status": "ok"}


@router.post("/trash")
def move_to_trash(req: ToggleRequest, user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    src = safe_path(req.path, u)
    dst_dir = os.path.join(NAS_ROOT, ".trash", u)
    if not os.path.exists(dst_dir): 
        os.makedirs(dst_dir, mode=0o700)
        
    base = os.path.basename(src)
    dst = os.path.join(dst_dir, base)
    if os.path.exists(dst): 
        dst = os.path.join(dst_dir, f"{datetime.now().strftime('%m%d%H%M')}_{base}")
        
    if os.path.exists(src): 
        shutil.move(src, dst)
    return {"status": "ok"}


@router.post("/restore")
def restore_from_trash(req: ToggleRequest, user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    trash_src = os.path.join(NAS_ROOT, ".trash", u, os.path.basename(req.path))
    user_root = safe_path("", u)
    dst = os.path.join(user_root, os.path.basename(req.path))
    
    if os.path.exists(trash_src):
        if os.path.exists(dst): 
            dst = os.path.join(user_root, f"restored_{os.path.basename(req.path)}")
        shutil.move(trash_src, dst)
    return {"status": "ok"}


@router.post("/mkdir")
def make_dir(req: ItemRequest, user: dict = Depends(get_current_user_obj)):
    p = safe_path(os.path.join(req.path, req.name), user["username"])
    if not os.path.exists(p): 
        os.makedirs(p)
    log_event(user["username"], f"Cloud storage: Created folder {req.name}")
    return {"status": "ok"}


@router.post("/upload")
async def upload_nas(path: str = Form(""), file: UploadFile = File(...), user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    user_root = safe_path("", u)
    
    if get_dir_size(user_root) + file.size > QUOTA_PER_USER:
        raise HTTPException(status_code=400, detail="Quota Exceeded (Limit 1GB)")
        
    t = safe_path(os.path.join(path, file.filename), u)
    with open(t, "wb") as b: 
        shutil.copyfileobj(file.file, b)
        
    log_event(u, f"Cloud storage: Uploaded {file.filename}")
    return {"status": "ok"}


@router.get("/download")
def download_nas(path: str, owner: Optional[str] = None, user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    target_owner = owner if owner else u
    
    if target_owner != u:
        meta = load_meta()
        shared = any(x["owner"] == target_owner and x["path"] == path and x["target"] == u for x in meta["shares"])
        if not shared: 
            raise HTTPException(status_code=403, detail="Access Denied (Not Shared)")
    
    p = safe_path(path, target_owner)
    log_event(u, f"Cloud storage: Downloaded/Previewed {os.path.basename(path)} (Owner: {target_owner})")
    
    return FileResponse(p, filename=os.path.basename(path))


@router.post("/delete")
def delete_nas(req: ToggleRequest, user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    p = ""
    trash_path = os.path.join(NAS_ROOT, ".trash", u, os.path.basename(req.path))
    
    if os.path.exists(trash_path): 
        p = trash_path
    else: 
        p = safe_path(req.path, u)
    
    if os.path.exists(p):
        if os.path.isdir(p): 
            shutil.rmtree(p)
        else: 
            os.remove(p)
        log_event(u, f"Cloud storage: Permanently deleted {os.path.basename(p)}")
        
    return {"status": "ok"}
