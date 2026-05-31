from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, VMAccount
from app.models import VMAccountCreate
from app.utils import get_current_user_obj, log_event

router = APIRouter(prefix="/api/proxmox", tags=["proxmox_users"])

@router.get("/vm_users")
def get_vm_users(user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    accounts = db.query(VMAccount).all()
    res = []
    for acc in accounts:
        res.append({
            "id": acc.id,
            "username": acc.username,
            "password": acc.password,
            "vmid": acc.vmid,
            "description": acc.description
        })
    return res

@router.post("/vm_users")
def create_vm_user(req: VMAccountCreate, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    # 檢查是否已存在
    existing = db.query(VMAccount).filter(VMAccount.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="此帳號名稱已存在")
    
    new_acc = VMAccount(
        username=req.username,
        password=req.password,
        vmid=req.vmid,
        description=req.description
    )
    db.add(new_acc)
    db.commit()
    db.refresh(new_acc)
    
    log_event(user["username"], f"VM_USER: Created account {req.username} for VM {req.vmid}")
    return {"status": "ok", "id": new_acc.id}

@router.delete("/vm_users/{id}")
def delete_vm_user(id: int, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    acc = db.query(VMAccount).filter(VMAccount.id == id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="找不到此帳號")
    
    username = acc.username
    db.delete(acc)
    db.commit()
    
    log_event(user["username"], f"VM_USER: Deleted account {username}")
    return {"status": "ok"}

@router.get("/console_url")
def get_console_url(vmid: int, node: str, vm_type: str = "qemu", user: dict = Depends(get_current_user_obj)):
    # 這裡的 PVE 宿主機 IP 為 100.124.203.61 (Tailscale IP)，確保全域皆可連線
    pve_ip = "100.124.203.61"
    console_type = "kvm" if vm_type == "qemu" else "lxc"
    url = f"https://{pve_ip}:8006/?console={console_type}&novnc=1&vmid={vmid}&vmtype={vm_type}&node={node}"
    return {"url": url}
