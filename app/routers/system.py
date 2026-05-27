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
from app.config import SYS_ROOT, NAS_ROOT, BLYNK_TOKEN
from app.database import get_db, AuditLog

router = APIRouter(tags=["system"])

# --- 網際網路測速器 (每 300 秒更新) ---
import threading
import speedtest

SPEEDTEST_STATE = {
    "last_check": 0,
    "up_mbps": 0.0,
    "down_mbps": 0.0,
    "running": False
}

def perform_speedtest():
    global SPEEDTEST_STATE
    try:
        SPEEDTEST_STATE["running"] = True
        st = speedtest.Speedtest()
        st.get_best_server()
        down = st.download() / 1000000.0
        up = st.upload() / 1000000.0
        SPEEDTEST_STATE["down_mbps"] = round(down, 2)
        SPEEDTEST_STATE["up_mbps"] = round(up, 2)
        SPEEDTEST_STATE["last_check"] = time.time()
    except Exception as e:
        print(f"Speedtest Error: {e}")
    finally:
        SPEEDTEST_STATE["running"] = False

# --- GitHub 智能監聽器 (120 秒快取) ---
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
    headers = {}
    if token and token != "your_github_token_here":
        headers["Authorization"] = f"token {token}"

    try:
        r = requests.get("https://api.github.com/repos/deven951130/Absolute-Axis", headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            GITHUB_STATE["data"]["online"] = True
            GITHUB_STATE["data"]["stars"] = d.get("stargazers_count", 0)
            GITHUB_STATE["data"]["repo_name"] = d.get("full_name", "Absolute-Axis")

            cr = requests.get("https://api.github.com/repos/deven951130/Absolute-Axis/commits?per_page=1", headers=headers, timeout=5)
            if cr.status_code == 200:
                cd = cr.json()[0]
                GITHUB_STATE["data"]["last_commit"] = cd["commit"]["message"].split("\n")[0]
                GITHUB_STATE["data"]["commit_time"] = cd["commit"]["author"]["date"]
        elif r.status_code == 403:
            GITHUB_STATE["data"]["online"] = False
            GITHUB_STATE["data"]["last_commit"] = "GitHub Rate Limit (Use Token)"
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


# ==================== 拆分後的獨立端點 ====================

@router.get("/api/system/metrics")
def get_metrics(user: dict = Depends(get_current_user_obj)):
    """高頻端點（每 5 秒）：CPU、RAM、磁碟、頻寬"""
    global SPEEDTEST_STATE

    sys_usage = shutil.disk_usage(SYS_ROOT)
    nas_usage = shutil.disk_usage(NAS_ROOT)

    now = time.time()
    if not SPEEDTEST_STATE["running"] and (now - SPEEDTEST_STATE["last_check"] > 300):
        SPEEDTEST_STATE["running"] = True
        threading.Thread(target=perform_speedtest, daemon=True).start()

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
            "up": f"{SPEEDTEST_STATE['up_mbps']:.2f} Mbps" if SPEEDTEST_STATE['last_check'] > 0 else "測速中...",
            "down": f"{SPEEDTEST_STATE['down_mbps']:.2f} Mbps" if SPEEDTEST_STATE['last_check'] > 0 else "測速中..."
        }
    }


@router.get("/api/system/sensors")
def get_sensors(user: dict = Depends(get_current_user_obj)):
    """中頻端點（每 30 秒）：溫濕度、Minecraft 狀態、Public IP"""
    temps = psutil.sensors_temperatures()
    cpu_temp = 0
    if temps and 'coretemp' in temps:
        cpu_temp = temps['coretemp'][0].current
    elif temps and 'cpu_thermal' in temps:
        cpu_temp = temps['cpu_thermal'][0].current
    else:
        cpu_temp = 30 + (psutil.cpu_percent() * 0.4)

    room_temp = round(cpu_temp, 1)
    room_humid = 45
    if BLYNK_TOKEN:
        try:
            r1 = requests.get(f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&v1", timeout=5)
            r2 = requests.get(f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&v2", timeout=5)
            if r1.status_code == 200 and r2.status_code == 200:
                t_str = r1.text.strip('[]" \n\r\t')
                h_str = r2.text.strip('[]" \n\r\t')
                if t_str and h_str:
                    room_temp = float(t_str)
                    room_humid = float(h_str)
            else:
                room_temp = 99.9
                room_humid = 99
        except Exception as e:
            print(f"Blynk Fetch Error: {e}")
            room_temp = 88.8
            room_humid = 88

    public_ip = "Unknown"
    try:
        ip_req = requests.get("https://api.ipify.org?format=json", timeout=2)
        if ip_req.status_code == 200:
            public_ip = ip_req.json().get("ip", "Unknown")
    except:
        pass

    mc_online = False
    mc_specs = {"ram": "16GB", "cores": 8}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("192.168.0.130", 25565)) == 0:
                mc_online = True
    except:
        pass

    return {
        "sensors": {"temp": room_temp, "humid": room_humid},
        "minecraft": {
            "online": mc_online,
            "ip": public_ip,
            "port": 25565,
            "specs": mc_specs
        }
    }


@router.get("/api/system/github")
def get_github(user: dict = Depends(get_current_user_obj)):
    """低頻端點（每 120 秒）：GitHub 倉庫狀態"""
    return check_github_status()


# ==================== 向下相容 alias ====================

@router.get("/api/system_status")
def get_status(user: dict = Depends(get_current_user_obj)):
    """向下相容端點：合併三個子端點的資料（保留給舊前端使用）"""
    metrics = get_metrics(user)
    sensors_data = get_sensors(user)
    github_data = get_github(user)
    return {**metrics, **sensors_data, "github": github_data}


# ==================== 其他系統端點 ====================

@router.get("/api/sys_config")
def get_sys_config(user: dict = Depends(get_current_user_obj)):
    up_s = time.time() - psutil.boot_time()
    up_time = f"up {int(up_s // 3600)}h {int((up_s % 3600) // 60)}m"

    gpu_info = "VMware SVGA II"
    try:
        if os.path.exists("/proc/driver/nvidia/version"):
            gpu_info = "NVIDIA GeForce RTX"
    except:
        pass

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
    import threading
    def die():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=die, daemon=True).start()
    return {"status": "restarting"}
