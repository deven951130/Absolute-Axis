from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app.database import get_db, Gig
from app.models import GigCreate, GigReject
from app.utils import get_current_user_obj, get_current_user_obj_optional, log_event

router = APIRouter(prefix="/api/gigs", tags=["gigs"])

@router.get("")
def list_gigs(db: Session = Depends(get_db)):
    gigs = db.query(Gig).order_by(Gig.id.desc()).all()
    res = []
    for g in gigs:
        res.append({
            "id": g.id,
            "title": g.title,
            "description": g.description,
            "budget": g.budget,
            "creator": g.creator,
            "worker": g.worker,
            "status": g.status,
            "reject_reason": g.reject_reason,
            "contact": g.contact,
            "created_at": g.created_at.isoformat()
        })
    return res

@router.post("")
def create_gig(req: GigCreate, user: dict = Depends(get_current_user_obj_optional), db: Session = Depends(get_db)):
    creator_name = "Guest"
    if user:
        creator_name = user["username"]
    else:
        if not req.contact or not req.contact.strip():
            raise HTTPException(status_code=400, detail="未登入訪客必須提供聯絡方式")
            
    new_gig = Gig(
        title=req.title,
        description=req.description,
        budget=req.budget,
        creator=creator_name,
        contact=req.contact if not user else None,
        status="Open"
    )
    db.add(new_gig)
    db.commit()
    db.refresh(new_gig)
    
    log_name = user["username"] if user else f"Guest ({req.contact})"
    log_event(log_name, f"GIG: Published a new gig [{req.title}] with budget {req.budget}")
    return {"status": "ok", "id": new_gig.id}

@router.post("/{id}/accept")
def accept_gig(id: int, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    gig = db.query(Gig).filter(Gig.id == id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="找不到該案件")
    
    if gig.status != "Open":
        raise HTTPException(status_code=400, detail="該案件已被承接或已完成")
        
    if gig.creator == user["username"]:
        raise HTTPException(status_code=400, detail="發案人無法承接自己發佈的案件")
        
    gig.worker = user["username"]
    gig.status = "Assigned"
    db.commit()
    
    log_event(user["username"], f"GIG: Accepted gig [{gig.title}] published by {gig.creator}")
    return {"status": "ok"}

@router.post("/{id}/complete")
def complete_gig(id: int, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    gig = db.query(Gig).filter(Gig.id == id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="找不到該案件")
        
    if gig.status != "Assigned":
        raise HTTPException(status_code=400, detail="該案件目前未被承接")
        
    # 發案人或接案人都可以標記完成
    if user["username"] != gig.creator and user["username"] != gig.worker and user.get("role") not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="權限不足，僅發案人、接案人或管理員可標記完成")
        
    gig.status = "Completed"
    db.commit()
    
    log_event(user["username"], f"GIG: Completed gig [{gig.title}]")
    return {"status": "ok"}

@router.delete("/{id}")
def delete_gig(id: int, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    gig = db.query(Gig).filter(Gig.id == id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="找不到該案件")
        
    if gig.creator != user["username"] and user.get("role") not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅發案人或管理員可以刪除案件")
        
    db.delete(gig)
    db.commit()
    
    log_event(user["username"], f"GIG: Deleted gig [{gig.title}]")
    return {"status": "ok"}

@router.post("/{id}/reject")
def reject_gig(id: int, req: GigReject, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    gig = db.query(Gig).filter(Gig.id == id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="找不到該案件")
    
    if gig.status != "Open":
        raise HTTPException(status_code=400, detail="只能拒絕開放承接的案件")
        
    if gig.creator == user["username"]:
        raise HTTPException(status_code=400, detail="發案人無法拒絕自己發佈的案件")
        
    gig.status = "Rejected"
    gig.reject_reason = req.reason
    db.commit()
    
    log_event(user["username"], f"GIG: Rejected gig [{gig.title}] published by {gig.creator} for reason: {req.reason}")
    return {"status": "ok"}
