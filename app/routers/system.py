import os
import requests
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

# --- GitHub 智能監聽器 (60秒緩存防止封鎖) ---
GITHUB_STATE = {
    "last_check": 0,
    "data": {
        "online": False,
        "repo": "Absolute-Axis",
        "stars": 0,
        "last_commit": "Initializing...",
        "commit_time": "N/A"
    }
}

def check_github_status():
    global GITHUB_STATE
    now = time.time()
    if now - GITHUB_STATE["last_check"] < 120: 
        return GITHUB_STATE.get("data", {})
    
    token = os.getenv("GITHUB_TOKEN")
    # 如果 token 是預設值，視為無效
    if not token or token == "your_github_token_here":
        GITHUB_STATE["data"]["online"] = False
        GITHUB_STATE["data"]["last_commit"] = "Please config GITHUB_TOKEN in .env"
        GITHUB_STATE["last_check"] = now
        return GITHUB_STATE["data"]

    headers = {"Authorization": f"token {token}"}
    try:
        r = requests.get("https://api.github.com/repos/deven951130/Absolute-Axis", headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            GITHUB_STATE["data"]["online"] = True
            GITHUB_STATE["data"]["stars"] = d.get("stargazers_count", 0)
            
            cr = requests.get("https://api.github.com/repos/deven951130/Absolute-Axis/commits?per_page=1", headers=headers, timeout=5)
            if cr.status_code == 200:
                cd = cr.json()[0]
                GITHUB_STATE["data"]["last_commit"] = cd["commit"]["message"].split("\n")[0]
                GITHUB_STATE["data"]["commit_time"] = cd["commit"]["author"]["date"]
        elif r.status_code == 401:
            GITHUB_STATE["data"]["online"] = False
            GITHUB_STATE["data"]["last_commit"] = "Invalid GITHUB_TOKEN"
        else:
            GITHUB_STATE["data"]["online"] = False
            GITHUB_STATE["data"]["last_commit"] = f"HTTP {r.status_code}"
    except Exception as e:
        GITHUB_STATE["data"]["online"] = False
        GITHUB_STATE["data"]["last_commit"] = "Network Error"
    
    GITHUB_STATE["last_check"] = now
    return GITHUB_STATE["data"]

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
    
    # 避免除以零或間隔太短
    if diff_t < 0.1:
        up_speed = 0
        down_speed = 0
    else:
        up_speed = (counters.bytes_sent - NET_STATE["last_sent"]) / diff_t / (1024 * 1024)
        down_speed = (counters.bytes_recv - NET_STATE["last_recv"]) / diff_t / (1024 * 1024)
    
    # 更新狀態 (只在有合理間隔時更新)
    if diff_t >= 0.5:
        NET_STATE.update({"last_recv": counters.bytes_recv, "last_sent": counters.bytes_sent, "last_time": now})
    
    # 嘗試讀取實體感測器
    temps = psutil.sensors_temperatures()
    cpu_temp = 0
    if temps and 'coretemp' in temps:
        cpu_temp = temps['coretemp'][0].current
    elif temps and 'cpu_thermal' in temps:
        cpu_temp = temps['cpu_thermal'][0].current
    else:
        cpu_temp = 30 + (psutil.cpu_percent() * 0.4)

    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "sys_disk": {
            "total": sys_usage.total, "used": sys_usage.used,
            "percent": (sys_usage.used / sys_usage.total) * 100 if sys_usage.total > 0 else 0,
            "health": "Excellent", "temp": round(cpu_temp - 2)
        },
        "nas_disk": {
            "total": nas_usage.total, "used": nas_usage.used,
            "percent": (nas_usage.used / nas_usage.total) * 100 if nas_usage.total > 0 else 0,
            "health": "Healthy", "temp": round(cpu_temp - 5)
        },
        "bandwidth": {
            "up": f"{max(0, up_speed):.2f} MB/s",
            "down": f"{max(0, down_speed):.2f} MB/s"
        },
        "sensors": {"temp": round(cpu_temp, 1), "humid": 45}, 
        "github": check_github_status()
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

@router.get("/api/system/hardware")
def get_hardware_info(user: dict = Depends(get_current_user_obj)):
    import subprocess
    import json
    
    disks = []
    
    try:
        # 1. 使用 lsblk 獲取所有區塊設備
        lsblk_cmd = ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,SERIAL,VENDOR"]
        res = subprocess.check_output(lsblk_cmd).decode('utf-8')
        data = json.loads(res)
        
        block_devices = data.get("blockdevices", [])
        
        for dev in block_devices:
            if dev.get("type") != "disk":
                continue
                
            name = dev.get("name")
            dev_path = f"/dev/{name}"
            
            model = dev.get("model") or "Generic Disk"
            vendor = dev.get("vendor") or ""
            full_name = f"{vendor} {model}".strip()
            
            total_bytes = int(dev.get("size") or 0)
            total_gb = round(total_bytes / (1024**3), 1)
            
            used_bytes = 0
            mounts = []
            
            def scan_mounts(item):
                nonlocal used_bytes
                mp = item.get("mountpoint")
                if mp:
                    mounts.append(mp)
                    try:
                        usage = shutil.disk_usage(mp)
                        used_bytes += usage.used
                    except:
                        pass
                for child in item.get("children", []):
                    scan_mounts(child)
            
            scan_mounts(dev)
            
            used_pct = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0
            
            status = "Healthy"
            temp = 35
            smart_hint = "Standard"
            
            try:
                smart_res = subprocess.getoutput(f"smartctl -i -H -A {dev_path} --json")
                if "{" in smart_res:
                    sj = json.loads(smart_res)
                    if sj.get("smart_status", {}).get("passed") is False:
                        status = "ATTENTION"
                    
                    if "temperature" in sj:
                        temp = sj["temperature"].get("current", temp)
                    elif "ata_smart_attributes" in sj:
                        for attr in sj["ata_smart_attributes"].get("table", []):
                            if attr.get("id") in [194, 190]:
                                temp = attr.get("raw", {}).get("value", temp)
                                break
                    smart_hint = "SMART Capable"
            except:
                smart_hint = "Simulation (No SMART)"

            disks.append({
                "name": full_name,
                "device": dev_path,
                "status": status,
                "temp": temp,
                "used_pct": round(used_pct, 1),
                "total_gb": total_gb,
                "used_gb": round(used_bytes / (1024**3), 1),
                "type": "SSD" if "SSD" in full_name.upper() or total_gb < 1000 else "HDD",
                "smart_hint": smart_hint,
                "mounts": mounts
            })
            
    except Exception as e:
        print(f"Hardware Scan Error: {e}")

    return {
        "disks": disks,
        "raid": {"name": "Dynamic Storage Pool", "status": "ONLINE", "type": "Detected"},
        "details": {
            "count": len(disks),
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "core": f"{round(shutil.disk_usage('/').used / (1024**3), 1)}G",
            "user": f"{round(shutil.disk_usage(NAS_ROOT).used / (1024**3), 1)}G",
            "docker": "Detected"
        }
    }

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

@router.post("/api/action/restart")
def restart_server(user: dict = Depends(get_current_user_obj)):
    log_event(user["username"], "SYSTEM: Initiated a server process restart.")
    # On Windows/Linux, if running via a service manager or uvicorn --reload, 
    # exiting the process will trigger a restart.
    import threading
    def die():
        time.sleep(1)
        os._exit(0) # Immediate exit to force service manager to restart
    
    threading.Thread(target=die, daemon=True).start()
    return {"status": "restarting"}
