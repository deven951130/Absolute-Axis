import os
import re
import json
import subprocess
import requests
import psutil
import socket
import shutil
import platform
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import MessageRequest
from app.utils import get_current_user_obj, log_event, get_dir_size, require_admin
from app.config import SYS_ROOT, NAS_ROOT, BLYNK_TOKEN, BASE_PATH
from app.database import get_db, AuditLog
from app.routers.minecraft import MC_LXC_IP, MC_LXC_PORT, mc_paused

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
    nas_used_bytes = get_dir_size(NAS_ROOT)
    nas_total_bytes = shutil.disk_usage(NAS_ROOT).total

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
            "total": nas_total_bytes, "used": nas_used_bytes,
            "percent": (nas_used_bytes / nas_total_bytes) * 100 if nas_total_bytes > 0 else 0,
            "health": "Healthy", "temp": round(cpu_temp - 5)
        },
        "bandwidth": {
            "up": f"{SPEEDTEST_STATE['up_mbps']:.2f} Mbps" if SPEEDTEST_STATE['last_check'] > 0 else "測速中...",
            "down": f"{SPEEDTEST_STATE['down_mbps']:.2f} Mbps" if SPEEDTEST_STATE['last_check'] > 0 else "測速中..."
        }
    }


def mask_ip(ip: str) -> str:
    if not ip or ip == "Unknown":
        return ip
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.**.***"
    return ip


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
    # 省電中（autopause）連遊戲埠會把伺服器叫醒 → 只看狀態，不連線
    mc_is_paused = mc_paused()
    if mc_is_paused:
        mc_online = True
    else:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if MC_LXC_IP and s.connect_ex((MC_LXC_IP, MC_LXC_PORT)) == 0:
                    mc_online = True
        except:
            pass

    is_admin = user.get("role") in ("admin", "Administrator")
    display_ip = public_ip if is_admin else mask_ip(public_ip)

    return {
        # source：溫濕度的來源；None＝沒有感測器（上面的數字是用 CPU 溫度估的，前端不當成房間溫度顯示）
        "sensors": {"temp": room_temp, "humid": room_humid, "source": "blynk" if BLYNK_TOKEN else None},
        "minecraft": {
            "online": mc_online,
            "ip": display_ip,
            "port": MC_LXC_PORT,
            "paused": mc_is_paused,
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


# ==================== NAS 管理：硬碟、儲存池（/api/system/hardware） ====================
# 只讀資料、不改任何設定。主控台通常跑在容器裡（privileged、掛 /dev），所以：
# - 看得到所有硬碟（lsblk、smartctl 走 /dev），/proc/mdstat 是主機核心的；
# - 但看不到主機自己掛載的檔案系統（掛載點在主機的 mount namespace），這種分割區算不出已用空間，畫面上會說明原因。

HW_CMD_TIMEOUT = 15
DOCKER_USAGE_TTL = 300
BTRFS_SYSFS = "/sys/fs/btrfs"
_DOCKER_USAGE_CACHE = {"ts": 0.0, "bytes": None}

# 屬於儲存池成員的檔案系統：本身不會被掛載，不算「主機另外掛載」
POOL_MEMBER_FSTYPES = {"linux_raid_member", "zfs_member", "LVM2_member", "swap", "crypto_LUKS"}
_STANDBY_RE = re.compile(r"in (STANDBY|SLEEP) mode", re.IGNORECASE)
# SSD 剩餘壽命（ATA 屬性的正規化值就是剩餘 %）：各廠商用的編號不同
SSD_LIFE_ATTR_IDS = (231, 169, 202, 233, 177)


def _run_cmd(argv, timeout=HW_CMD_TIMEOUT):
    """執行指令，回傳 (exit code, stdout)；指令不存在或逾時回傳 None。"""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _in_container() -> bool:
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")


def _as_bool(v):
    """lsblk 舊版輸出 "0"/"1"，新版輸出 true/false。"""
    if isinstance(v, bool):
        return v
    if v in ("1", 1):
        return True
    if v in ("0", 0):
        return False
    return None


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _lsblk_devices():
    out = _run_cmd(["lsblk", "-J", "-b", "-o",
                    "NAME,SIZE,TYPE,ROTA,TRAN,MOUNTPOINT,FSTYPE,UUID,LABEL,MODEL,SERIAL,VENDOR"])
    if not out or out[0] != 0:
        return None
    try:
        return json.loads(out[1]).get("blockdevices", [])
    except ValueError:
        return None


def _walk(dev):
    yield dev
    for child in dev.get("children") or []:
        yield from _walk(child)


def _disk_usage(dev):
    """看得到的掛載點的已用空間；回傳 (used_bytes, size_of_visible, mounts, hidden 分割區數)。"""
    used = size = 0
    mounts, hidden = [], 0
    for item in _walk(dev):
        mp = item.get("mountpoint")
        fstype = item.get("fstype")
        if mp and mp != "[SWAP]":
            mounts.append(mp)
            try:
                u = shutil.disk_usage(mp)
                used += u.used
                size += u.total
            except OSError:
                pass
        elif fstype and fstype not in POOL_MEMBER_FSTYPES:
            hidden += 1
    return used, size, mounts, hidden


def _smart_attr(table, attr_id):
    for attr in table:
        if attr.get("id") == attr_id:
            return attr
    return None


def parse_smart(sj: dict) -> dict:
    """從 smartctl --json 取重點屬性；拿不到的欄位是 None。"""
    smart = {"reallocated": None, "pending": None, "power_on_hours": None, "life_left": None, "temp": None}
    temp = (sj.get("temperature") or {}).get("current")
    hours = (sj.get("power_on_time") or {}).get("hours")

    table = (sj.get("ata_smart_attributes") or {}).get("table") or []
    if table:
        def raw(attr_id):
            a = _smart_attr(table, attr_id)
            return (a.get("raw") or {}).get("value") if a else None
        smart["reallocated"] = raw(5)
        smart["pending"] = raw(197)
        if hours is None:
            hours = raw(9)
        if temp is None:
            t = raw(194) if raw(194) is not None else raw(190)
            # 有些硬碟把最高／最低溫度包在高位元組
            temp = t & 0xFF if isinstance(t, int) else None
        for attr_id in SSD_LIFE_ATTR_IDS:
            a = _smart_attr(table, attr_id)
            if a and isinstance(a.get("value"), int):
                smart["life_left"] = max(0, min(100, a["value"]))
                break

    nvme = sj.get("nvme_smart_health_information_log") or {}
    if nvme:
        if isinstance(nvme.get("percentage_used"), int):
            smart["life_left"] = max(0, 100 - nvme["percentage_used"])
        if hours is None:
            hours = nvme.get("power_on_hours")
        if temp is None:
            temp = nvme.get("temperature")

    smart["power_on_hours"] = hours
    smart["temp"] = temp
    return smart


def read_smart(dev_path: str) -> dict:
    """smartctl -n standby：硬碟在休眠就不讀（不把它叫醒）。

    status：OK／WARNING（有重新配置或待處理磁區）／FAILING（SMART 自評失敗）／STANDBY／UNKNOWN
    """
    res = {"status": "UNKNOWN", "standby": False, "smart": None, "note": None}
    out = _run_cmd(["smartctl", "-n", "standby", "-i", "-H", "-A", "--json", dev_path])
    if out is None:
        res["note"] = "沒有 smartctl 指令"
        return res
    _code, text = out
    if _STANDBY_RE.search(text or ""):
        res["status"] = "STANDBY"
        res["standby"] = True
        return res
    try:
        sj = json.loads(text)
    except ValueError:
        res["note"] = "無法讀取 SMART"
        return res
    if not isinstance(sj, dict):
        res["note"] = "無法讀取 SMART"
        return res
    for msg in (sj.get("smartctl") or {}).get("messages") or []:
        if _STANDBY_RE.search(msg.get("string", "")):
            res["status"] = "STANDBY"
            res["standby"] = True
            return res

    smart = parse_smart(sj)
    passed = (sj.get("smart_status") or {}).get("passed")
    if passed is False:
        res["status"] = "FAILING"
    elif (smart["reallocated"] or 0) > 0 or (smart["pending"] or 0) > 0:
        res["status"] = "WARNING"
    elif passed is True:
        res["status"] = "OK"
    else:
        res["note"] = "這顆硬碟不支援或沒有開啟 SMART"
    res["smart"] = smart
    return res


def _disk_type(dev):
    rota = _as_bool(dev.get("rota"))
    if rota is None:
        return None
    return "HDD" if rota else "SSD"


def scan_disks(devices, in_container: bool) -> list:
    disks = []
    for dev in devices:
        name = dev.get("name") or ""
        if dev.get("type") != "disk" or name.startswith(("zram", "ram", "loop")):
            continue
        dev_path = f"/dev/{name}"
        model = (dev.get("model") or "").strip()
        vendor = (dev.get("vendor") or "").strip()
        full_name = f"{vendor} {model}".strip() or name

        total_bytes = _as_int(dev.get("size")) or 0
        used_bytes, visible_size, mounts, hidden = _disk_usage(dev)

        used_pct = used_gb = None
        usage_note = None
        if mounts and visible_size > 0:
            used_gb = round(used_bytes / (1024 ** 3), 1)
            used_pct = round(used_bytes / visible_size * 100, 1)
            if hidden:
                usage_note = f"另有 {hidden} 個分割區掛載在主機上，容器內看不到，已用只計入看得到的部分"
        elif hidden:
            usage_note = ("掛載在主機上，主控台在容器內看不到掛載點，所以算不出已用空間"
                          if in_container else "沒有掛載，算不出已用空間")
        elif any(item.get("fstype") in POOL_MEMBER_FSTYPES for item in _walk(dev)):
            usage_note = "屬於儲存池，用量見儲存池"
        else:
            usage_note = "沒有檔案系統"

        smart = read_smart(dev_path)
        disks.append({
            "name": full_name,
            "device": dev_path,
            "type": _disk_type(dev),
            "transport": dev.get("tran"),
            "total_gb": round(total_bytes / (1024 ** 3), 1),
            "used_gb": used_gb,
            "used_pct": used_pct,
            "mounts": mounts,
            "hidden_partitions": hidden,
            "usage_note": usage_note,
            "status": smart["status"],
            "standby": smart["standby"],
            "smart": smart["smart"],
            "smart_note": smart["note"],
            "temp": (smart["smart"] or {}).get("temp"),
        })
    return disks


_MD_HEAD_RE = re.compile(r"^(md\S*)\s*:\s*(active|inactive)\s*(?:\((\S+)\)\s*)?(raid\d+|linear|multipath)?\s*(.*)$")


def parse_mdstat(text: str) -> list:
    """/proc/mdstat → 軟體 RAID（mdadm）清單。"""
    pools = []
    if not text:
        return pools
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _MD_HEAD_RE.match(line.strip())
        if not m:
            continue
        name, state, _ro, level, rest = m.groups()
        members = [re.sub(r"\[\d+\]", "", tok) for tok in rest.split()]
        failed = [tok.replace("(F)", "") for tok in members if tok.endswith("(F)")]
        members = [tok.replace("(F)", "").replace("(S)", "") for tok in members]
        detail = " ".join(l.strip() for l in lines[i + 1:i + 3])
        status = "ONLINE"
        if state == "inactive":
            status = "INACTIVE"
        elif failed or re.search(r"\[U*_+[U_]*\]", detail):
            status = "DEGRADED"
        if re.search(r"(recovery|resync|reshape)\s*=", detail):
            status = "REBUILDING" if status != "INACTIVE" else status
        pools.append({"kind": "mdadm", "name": name, "level": level or "unknown",
                      "status": status, "devices": members, "note": None})
    return pools


def detect_zfs(devices) -> list:
    out = _run_cmd(["zpool", "list", "-H", "-o", "name,health"])
    if out is not None:
        pools = []
        if out[0] == 0:
            for line in out[1].splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    pools.append({"kind": "zfs", "name": parts[0], "level": "zfs",
                                  "status": parts[1].strip(), "devices": [], "note": None})
        return pools
    # 容器裡沒有 zpool 指令：從 lsblk 的 zfs_member 認出池（狀態未知）
    groups = {}
    for dev in devices or []:
        for item in _walk(dev):
            if item.get("fstype") == "zfs_member":
                groups.setdefault(item.get("label") or item.get("uuid") or "zfs", []).append(item.get("name"))
    return [{"kind": "zfs", "name": label, "level": "zfs", "status": "UNKNOWN", "devices": members,
             "note": "主控台沒有 zpool 指令，讀不到池的狀態"} for label, members in groups.items()]


def detect_btrfs(devices) -> list:
    """多顆硬碟組成的 btrfs（同一個 UUID 出現在 ≥2 個裝置）；RAID 等級從 /sys/fs/btrfs 讀（掛載中才有）。"""
    groups = {}
    for dev in devices or []:
        for item in _walk(dev):
            if item.get("fstype") == "btrfs" and item.get("uuid"):
                g = groups.setdefault(item["uuid"], {"label": item.get("label"), "devices": []})
                g["devices"].append(item.get("name"))
    pools = []
    for uuid, g in groups.items():
        if len(g["devices"]) < 2:
            continue
        alloc = os.path.join(BTRFS_SYSFS, uuid, "allocation", "data")
        level, status, note = "btrfs", "UNKNOWN", "沒有掛載，讀不到 RAID 等級"
        if os.path.isdir(alloc):
            profiles = [p for p in os.listdir(alloc)
                        if os.path.isdir(os.path.join(alloc, p)) and (p.startswith("raid") or p in ("single", "dup"))]
            level = "btrfs " + "/".join(sorted(profiles)) if profiles else "btrfs"
            status, note = "ONLINE", None
        pools.append({"kind": "btrfs", "name": g["label"] or uuid[:8], "level": level,
                      "status": status, "devices": g["devices"], "note": note})
    return pools


def detect_pools(devices) -> list:
    return parse_mdstat(_read_text("/proc/mdstat")) + detect_zfs(devices) + detect_btrfs(devices)


def docker_usage_bytes():
    """Docker 映像＋容器可寫層＋volume＋build cache 的總量（docker system df）；5 分鐘快取，拿不到回傳 None。"""
    now = time.time()
    if now - _DOCKER_USAGE_CACHE["ts"] < DOCKER_USAGE_TTL:
        return _DOCKER_USAGE_CACHE["bytes"]
    total = None
    try:
        import docker
        df = docker.from_env(timeout=30).df()
        total = int(df.get("LayersSize") or 0)
        total += sum(int(c.get("SizeRw") or 0) for c in df.get("Containers") or [])
        total += sum(max(0, int((v.get("UsageData") or {}).get("Size") or 0)) for v in df.get("Volumes") or [])
        total += sum(int(b.get("Size") or 0) for b in df.get("BuildCache") or [] if not b.get("Shared"))
    except Exception as e:
        print(f"Docker df Error: {e}")
        total = None
    _DOCKER_USAGE_CACHE.update(ts=now, bytes=total)
    return total


def _gb(n):
    return f"{round(n / (1024 ** 3), 1)}G"


@router.get("/api/system/hardware")
def get_hardware_info(user: dict = Depends(get_current_user_obj)):
    in_container = _in_container()
    devices = _lsblk_devices()
    disks = scan_disks(devices, in_container) if devices is not None else []
    docker_bytes = docker_usage_bytes()

    return {
        "disks": disks,
        "disks_error": None if devices is not None else "無法執行 lsblk，讀不到硬碟清單",
        "pools": detect_pools(devices or []),
        "in_container": in_container,
        "details": {
            "count": len(disks),
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "core": _gb(shutil.disk_usage('/').used),
            "user": _gb(get_dir_size(NAS_ROOT)),
            "docker": _gb(docker_bytes) if docker_bytes is not None else None,
        }
    }


def mask_name(name: str) -> str:
    if not name:
        return ""
    if name.startswith("Guest"):
        return name
    is_ascii = all(ord(c) < 128 for c in name)
    if is_ascii:
        if len(name) <= 2:
            return "*" * len(name)
        return name[0] + "*" * (len(name) - 2) + name[-1]
    else:
        if len(name) <= 1:
            return name
        elif len(name) == 2:
            return name[0] + "*"
        elif len(name) == 3:
            return name[0] + "*" + name[2]
        else:
            return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_filename(filename: str) -> str:
    if not filename:
        return ""
    if "." in filename:
        base, ext = os.path.splitext(filename)
    else:
        base, ext = filename, ""
    if len(base) <= 3:
        base = "*" * len(base)
    else:
        keep = max(1, len(base) // 3)
        base = base[:keep] + "***" + base[-keep:]
    return base + ext


@router.get("/api/system/logs")
def get_logs(user: dict = Depends(get_current_user_obj), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(50).all()
    res = []
    is_admin = user.get("role") in ("admin", "Administrator")

    for log in reversed(logs):
        ts = log.timestamp.strftime("%H:%M:%S")
        username = log.username
        action = log.action

        if not is_admin:
            username = mask_name(username)
            if "Cloud storage: Uploaded " in action:
                fn = action.replace("Cloud storage: Uploaded ", "")
                action = f"Cloud storage: Uploaded {mask_filename(fn)}"
            elif "Cloud storage: Downloaded " in action:
                fn = action.replace("Cloud storage: Downloaded ", "")
                action = f"Cloud storage: Downloaded {mask_filename(fn)}"
            elif "Cloud storage: Permanently deleted " in action:
                fn = action.replace("Cloud storage: Permanently deleted ", "")
                action = f"Cloud storage: Permanently deleted {mask_filename(fn)}"
            elif "Cloud storage: Created folder " in action:
                fn = action.replace("Cloud storage: Created folder ", "")
                action = f"Cloud storage: Created folder {mask_filename(fn)}"

        res.append(f"[{ts}] [{username}] {action}")
    return res


@router.post("/api/system/message")
def post_msg(req: MessageRequest, user: dict = Depends(get_current_user_obj)):
    log_event(user["username"], f"BROADCAST: {req.message}")
    return {"status": "ok"}


@router.post("/api/action/restart")
def restart_server(user: dict = Depends(require_admin)):
    log_event(user["username"], "SYSTEM: Initiated a server process restart.")
    import threading
    def die():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=die, daemon=True).start()
    return {"status": "restarting"}


ANNOUNCEMENTS_FILE = os.path.join(BASE_PATH, "app", "announcements.json")

class AnnouncementCreate(BaseModel):
    content: str

def _load_announcements() -> list:
    if os.path.exists(ANNOUNCEMENTS_FILE):
        try:
            with open(ANNOUNCEMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_announcements(anns: list):
    with open(ANNOUNCEMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(anns, f, indent=4, ensure_ascii=False)


@router.get("/api/system/announcements")
def get_announcements(user: dict = Depends(get_current_user_obj)):
    """取得所有系統公告"""
    return _load_announcements()


@router.post("/api/system/announcements")
def create_announcement(req: AnnouncementCreate, user: dict = Depends(get_current_user_obj)):
    """發佈新公告（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員發布公告")
        
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="公告內容不得為空")
        
    anns = _load_announcements()
    
    new_ann = {
        "id": int(time.time() * 1000),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "author": user["username"],
        "content": content
    }
    
    anns.insert(0, new_ann)
    _save_announcements(anns)
    
    log_event(user["username"], f"ANNOUNCEMENT: Published new announcement: {content[:30]}")
    return {"status": "ok", "announcement": new_ann}

