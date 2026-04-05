import os
import shutil
import socket
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models import ItemRequest, ShareRequest, ToggleRequest
from app.utils import get_current_user_obj, safe_path, get_dir_size, log_event
from app.config import NAS_ROOT, QUOTA_PER_USER
from app.database import get_db, User, FileStar, FileShare

router = APIRouter(prefix="/api/nas", tags=["nas"])

@router.get("/list")
def list_nas_files(path: str = "", mode: str = "drive", user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    try:
        u = user["username"]
        items = []
        user_root = safe_path("", u)
        
        if mode == "drive":
            t = safe_path(path, u)
            if not os.path.exists(t): 
                return {"files": [], "quota_used": 0, "quota_total": QUOTA_PER_USER}
            
            starred_paths = [s.path for s in db.query(FileStar).filter(FileStar.username == u).all()]
            shared_paths = [s.path for s in db.query(FileShare).filter(FileShare.owner == u).all()]

            for e in os.scandir(t):
                try:
                    if e.name.startswith("."): continue
                    s = e.stat()
                    full_rel = (path.strip("/") + "/" + e.name).strip("/")
                    items.append({
                        "name": e.name, 
                        "is_dir": e.is_dir(), 
                        "size": s.st_size,
                        "modified": datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "ext": os.path.splitext(e.name)[1].lower() if not e.is_dir() else "folder",
                        "starred": full_rel in starred_paths,
                        "shared": full_rel in shared_paths
                    })
                except Exception as ex:
                    print(f"Error scanning entry {e.name}: {ex}")
                    continue
                
        elif mode == "starred":
            stars = db.query(FileStar).filter(FileStar.username == u).all()
            for s in stars:
                try:
                    p = safe_path(s.path, u)
                    if os.path.exists(p):
                        stat = os.stat(p)
                        items.append({
                            "name": os.path.basename(p), "is_dir": os.path.isdir(p), 
                            "size": stat.st_size, "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"), 
                            "ext": os.path.splitext(p)[1].lower(), "path": s.path, "starred": True
                        })
                except: continue
                        
        elif mode == "shared":
            shares = db.query(FileShare).filter(FileShare.target == u).all()
            for sh in shares:
                try:
                    p = safe_path(sh.path, sh.owner)
                    if os.path.exists(p):
                        stat = os.stat(p)
                        items.append({
                            "name": os.path.basename(p), "is_dir": os.path.isdir(p), 
                            "size": stat.st_size, "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"), 
                            "ext": os.path.splitext(p)[1].lower(), "path": sh.path, "owner": sh.owner
                        })
                except: continue
                        
        elif mode == "trash":
            trash_dir = os.path.join(NAS_ROOT, ".trash", u)
            if os.path.exists(trash_dir):
                for e in os.scandir(trash_dir):
                    try:
                        s = e.stat()
                        items.append({
                            "name": e.name, "is_dir": e.is_dir(), "size": s.st_size, 
                            "modified": datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M"), 
                            "ext": os.path.splitext(e.name)[1].lower()
                        })
                    except: continue
                    
        elif mode == "recent":
            all_files = []
            for r, d, f_names in os.walk(user_root):
                for f in f_names:
                    try:
                        if f.startswith("."): continue
                        p = os.path.join(r, f)
                        s = os.stat(p)
                        all_files.append({
                            "name": f, "is_dir": False, "size": s.st_size, 
                            "mtime": s.st_mtime, "path": os.path.relpath(p, user_root)
                        })
                    except: continue
            all_files.sort(key=lambda x: x["mtime"], reverse=True)
            items = [{
                "name": x["name"], "is_dir": x["is_dir"], "size": x["size"], 
                "modified": datetime.fromtimestamp(x["mtime"]).strftime("%Y-%m-%d %H:%M"), 
                "ext": os.path.splitext(x["name"])[1].lower(), "path": x["path"]
            } for x in all_files[:20]]

        return {
            "files": items if mode == "recent" else sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower())),
            "quota_used": get_dir_size(user_root), 
            "quota_total": QUOTA_PER_USER
        }
    except Exception as overall_ex:
        print(f"Overall NAS List Error: {overall_ex}")
        raise HTTPException(status_code=500, detail=f"Server internal error: {str(overall_ex)}")


@router.post("/toggle_star")
def toggle_star(req: ToggleRequest, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    u = user["username"]
    existing = db.query(FileStar).filter(FileStar.username == u, FileStar.path == req.path).first()
    if existing:
        db.delete(existing)
    else:
        db.add(FileStar(username=u, path=req.path))
    db.commit()
    return {"status": "ok"}


@router.get("/users")
def list_share_users(user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.username != user["username"]).all()
    return [{"username": u.username, "avatar": u.avatar} for u in users]


@router.post("/share")
def share_file(req: ShareRequest, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    u = user["username"]
    db.add(FileShare(owner=u, path=req.path, target=req.target_user))
    db.commit()
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
    if not os.path.exists(p): os.makedirs(p)
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
def download_nas(path: str, owner: Optional[str] = None, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    u = user["username"]
    target_owner = owner if owner else u
    if target_owner != u:
        shared = db.query(FileShare).filter(FileShare.owner == target_owner, FileShare.path == path, FileShare.target == u).first()
        if not shared: raise HTTPException(status_code=403, detail="Access Denied")
    p = safe_path(path, target_owner)
    log_event(u, f"Cloud storage: Downloaded {os.path.basename(path)}")
    return FileResponse(p, filename=os.path.basename(path))


@router.post("/delete")
def delete_nas(req: ToggleRequest, user: dict = Depends(get_current_user_obj)):
    u = user["username"]
    trash_path = os.path.join(NAS_ROOT, ".trash", u, os.path.basename(req.path))
    p = trash_path if os.path.exists(trash_path) else safe_path(req.path, u)
    if os.path.exists(p):
        if os.path.isdir(p): shutil.rmtree(p)
        else: os.remove(p)
        log_event(u, f"Cloud storage: Permanently deleted {os.path.basename(p)}")
    return {"status": "ok"}
