from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app.database import get_db, Feedback
from app.models import FeedbackCreate, FeedbackResolve
from app.utils import get_current_user_obj, log_event

router = APIRouter(prefix="/api/feedbacks", tags=["feedbacks"])

@router.get("")
def list_feedbacks(user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    is_admin = user.get("role") in ("admin", "Administrator")
    
    if is_admin:
        feedbacks = db.query(Feedback).order_by(Feedback.id.desc()).all()
    else:
        feedbacks = db.query(Feedback).filter(Feedback.creator == user["username"]).order_by(Feedback.id.desc()).all()
        
    res = []
    for f in feedbacks:
        res.append({
            "id": f.id,
            "title": f.title,
            "content": f.content,
            "creator": f.creator,
            "category": f.category,
            "status": f.status,
            "response": f.response,
            "created_at": f.created_at.isoformat()
        })
    return res

@router.post("")
def create_feedback(req: FeedbackCreate, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    new_fb = Feedback(
        title=req.title,
        content=req.content,
        category=req.category,
        creator=user["username"],
        status="Pending"
    )
    db.add(new_fb)
    db.commit()
    db.refresh(new_fb)
    
    log_event(user["username"], f"FEEDBACK: Submitted feedback [{req.title}] in category {req.category}")
    return {"status": "ok", "id": new_fb.id}

@router.post("/{id}/resolve")
def resolve_feedback(id: int, req: FeedbackResolve, user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    is_admin = user.get("role") in ("admin", "Administrator")
    if not is_admin:
        raise HTTPException(status_code=403, detail="僅限管理員回覆與處置意見反饋")
        
    fb = db.query(Feedback).filter(Feedback.id == id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="找不到該意見反饋")
        
    fb.response = req.response
    fb.status = "Resolved"
    db.commit()
    
    log_event(user["username"], f"FEEDBACK: Handled feedback [{fb.title}] -> Resolved")
    return {"status": "ok"}
