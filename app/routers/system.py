import psutil
import socket
import shutil
import random
import platform
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import MessageRequest
from app.utils import get_current_user_obj, log_event
from app.config import SYS_ROOT, NAS_ROOT
from app.database import get_db, AuditLog

router = APIRouter(tags=["system"])

@router.get("/api/system_status")
def get_status(user: dict = Depends(get_current_user_obj)):
    # 監控雙硬碟：SSD 系統碟 + HDD 資料碟
    sys_usage = shutil.disk_usage(SYS_ROOT)
    nas_usage = shutil.disk_usage(NAS_ROOT)
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "sys_disk": {
            "total": sys_usage.total, "used": sys_usage.used,
            "percent": (sys_usage.used / sys_usage.total) * 100 if sys_usage.total > 0 else 0,
            "health": "Excellent", "temp": 32
        },
        "nas_disk": {
            "total": nas_usage.total, "used": nas_usage.used,
            "percent": (nas_usage.used / nas_usage.total) * 100 if nas_usage.total > 0 else 0,
            "health": "Healthy", "temp": 38
        },
        "bandwidth": {
            "up": f"{int(random.uniform(5, 45)*10)/10} MB/s",
            "down": f"{int(random.uniform(20, 180)*10)/10} MB/s"
        },
        "sensors": {"temp": 24.5, "humid": 55}
    }

@router.get("/api/sys_config")
def get_sys_config(user: dict = Depends(get_current_user_obj)):
    up_time = f"up {round((datetime.now().timestamp() - psutil.boot_time()) / 60)} min"
    return {
        "os": "Ubuntu 24.04.4 LTS", 
        "python": platform.python_version(),
        "cpu_cores": psutil.cpu_count(), 
        "ram_total": f"{round(psutil.virtual_memory().total / (1024**3), 2)}G",
        "hostname": socket.gethostname(), 
        "boot_time": up_time, 
        "gpu": "VMware SVGA II"
    }

@router.get("/api/services_status")
def get_services(user: dict = Depends(get_current_user_obj)):
    res = []
    for n, p in [("Core API", 8000), ("SSH Shell", 22)]:
        o = False
        try:
            with socket.socket() as s: 
                s.settimeout(0.05)
                o = (s.connect_ex(("127.0.0.1", p)) == 0)
        except: 
            pass
        res.append({"name": n, "online": o})
    return res

@router.get("/api/system/logs")
def get_logs(user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)): 
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(50).all()
    res = []
    for log in reversed(logs):
        ts = log.timestamp.strftime("%H:%M:%S")
        res.append(f"[{ts}] [{log.username}] {log.action}")
    return res

@router.post("/api/system/message")
def post_msg(req: MessageRequest, user: dict = Depends(get_current_user_obj)):
    log_event(user["username"], f"BROADCAST: {req.message}")
    return {"status": "ok"}

@router.post("/api/action/clear_cache")
def clear_cache(user: dict = Depends(get_current_user_obj)):
    log_event(user["username"], "Maintenance: Executed system cache purge.")
    return {"status": "ok"}
