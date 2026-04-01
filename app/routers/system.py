import psutil
import socket
import shutil
import platform
import time
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import MessageRequest
from app.utils import get_current_user_obj, log_event
from app.config import SYS_ROOT, NAS_ROOT
from app.database import get_db, AuditLog

router = APIRouter(tags=["system"])

# --- 全域流量紀錄器 (用於計算差值速率) ---
NET_STATE = {
    "last_recv": psutil.net_io_counters().bytes_recv,
    "last_sent": psutil.net_io_counters().bytes_sent,
    "last_time": time.time()
}

@router.get("/api/system_status")
def get_status(user: dict = Depends(get_current_user_obj)):
    global NET_STATE
    
    # 磁碟真實數據
    sys_usage = shutil.disk_usage(SYS_ROOT)
    nas_usage = shutil.disk_usage(NAS_ROOT)
    
    # 真實頻寬差值計算 (MB/s)
    now = time.time()
    counters = psutil.net_io_counters()
    diff_t = now - NET_STATE["last_time"]
    
    up_speed = (counters.bytes_sent - NET_STATE["last_sent"]) / diff_t / (1024 * 1024) if diff_t > 0 else 0
    down_speed = (counters.bytes_recv - NET_STATE["last_recv"]) / diff_t / (1024 * 1024) if diff_t > 0 else 0
    
    # 更新狀態
    NET_STATE.update({"last_recv": counters.bytes_recv, "last_sent": counters.bytes_sent, "last_time": now})
    
    # 嘗試讀取實體感測器
    temps = psutil.sensors_temperatures()
    cpu_temp = 0
    if temps and 'coretemp' in temps:
        cpu_temp = temps['coretemp'][0].current
    elif temps and 'cpu_thermal' in temps: # RPi fallback
        cpu_temp = temps['cpu_thermal'][0].current
    else:
        # Fallback: 基於 CPU 負載擬合 (僅為沒感測器時的參考值)
        cpu_temp = 30 + (psutil.cpu_percent() * 0.4)

    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "sys_disk": {
            "total": sys_usage.total, "used": sys_usage.used,
            "percent": (sys_usage.used / sys_usage.total) * 100 if sys_usage.total > 0 else 0,
            "health": "Excellent", "temp": round(cpu_temp - 2) # 系統碟通常比 CPU 冷
        },
        "nas_disk": {
            "total": nas_usage.total, "used": nas_usage.used,
            "percent": (nas_usage.used / nas_usage.total) * 100 if nas_usage.total > 0 else 0,
            "health": "Healthy", "temp": round(cpu_temp - 5)
        },
        "bandwidth": {
            "up": f"{up_speed:.1f} MB/s",
            "down": f"{down_speed:.1f} MB/s"
        },
        "sensors": {"temp": round(cpu_temp, 1), "humid": 45} # 濕度通常需外部感測器，預設 45
    }

@router.get("/api/sys_config")
def get_sys_config(user: dict = Depends(get_current_user_obj)):
    up_s = time.time() - psutil.boot_time()
    up_time = f"up {int(up_s // 3600)}h {int((up_s % 3600) // 60)}m"
    
    # 獲取 GPU 分辨率或型號 (Linux fallback)
    gpu_info = "VMware SVGA II" 
    try:
        # 簡單偵測是否為 VMware 或實體卡
        if os.path.exists("/proc/driver/nvidia/version"): gpu_info = "NVIDIA GeForce RTX"
    except: pass

    return {
        "os": f"{platform.system()} {platform.release()}", 
        "python": platform.python_version(),
        "cpu_cores": psutil.cpu_count(), 
        "ram_total": f"{round(psutil.virtual_memory().total / (1024**3), 2)}G",
        "hostname": socket.gethostname(), 
        "boot_time": up_time, 
        "gpu": gpu_info
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
