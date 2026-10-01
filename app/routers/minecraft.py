import socket
import paramiko
import os
import re
import json
import shutil
import zipfile
import requests
from typing import Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from datetime import datetime

from app.models import MCCommandRequest
from app.utils import get_current_user_obj, log_event
from app.config import BASE_PATH

router = APIRouter(prefix="/api/minecraft", tags=["minecraft"])

# Minecraft 主機（LXC／VM）連線設定；沒設定 MC_HOST＝不使用 Minecraft 模組
# 內建容器模式：Minecraft 跑在這台主機的 Docker 容器（compose 的 minecraft profile）時填容器名稱。
# 指令改走容器內的 rcon-cli、模組包直接換資料目錄裡的 zip，不用 SSH
MC_CONTAINER = os.getenv("MC_CONTAINER", "").strip()
MC_DATA_DIR = os.getenv("MC_DATA_DIR", "").strip() or os.path.join(BASE_PATH, "minecraft-data")
MC_LXC_IP = os.getenv("MC_HOST", "").strip() or ("127.0.0.1" if MC_CONTAINER else "")
MC_LXC_PORT = int(os.getenv("MC_PORT", "").strip()) if os.getenv("MC_PORT", "").strip().isdigit() else 25565
# 玩家從外面連線用的網域（例如 DDNS 網域）；沒設定就不顯示
MC_PUBLIC_HOST = os.getenv("MC_PUBLIC_HOST", "").strip()
# SSH 帳密改由環境變數提供，不寫在程式碼裡（舊的明碼密碼已在 git 歷史中，請務必更換）
MC_SSH_USER = os.getenv("MC_SSH_USER", "root")
MC_SSH_PASS = os.getenv("MC_SSH_PASS", "")
MC_SCREEN_NAME = "mc"


def _check_online() -> bool:
    """快速 TCP 探測 Minecraft 是否存活。"""
    if not MC_LXC_IP:
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((MC_LXC_IP, MC_LXC_PORT)) == 0
    except Exception:
        return False


def _ssh_exec(command: str) -> Tuple[str, str]:
    """透過 SSH 在 LXC 容器中執行指令，回傳 (stdout, stderr)。"""
    if not MC_LXC_IP:
        raise HTTPException(status_code=503, detail="尚未設定 Minecraft 主機：請在 .env 設定 MC_HOST")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(MC_LXC_IP, username=MC_SSH_USER, password=MC_SSH_PASS, timeout=8)
        stdin, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        return out, err
    finally:
        client.close()


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_java_version_cache: dict = {}


def _mc_container():
    """取得 Minecraft 容器（容器模式）。"""
    try:
        import docker
        return docker.from_env().containers.get(MC_CONTAINER)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"找不到 Minecraft 容器 {MC_CONTAINER}：{e}")


def _container_env(container) -> dict:
    return dict(e.split("=", 1) for e in (container.attrs.get("Config", {}).get("Env") or []) if "=" in e)


def _container_exec(container, argv: list) -> str:
    """在容器內執行指令，回傳去掉色碼的輸出；非 0 結束碼視為失敗。"""
    res = container.exec_run(argv)
    out = _ANSI.sub("", (res.output or b"").decode(errors="replace")).strip()
    if res.exit_code != 0:
        raise RuntimeError(out or f"exit code {res.exit_code}")
    return out


def _container_status() -> Tuple[str, str, dict]:
    """容器模式的 (uptime, java_version, specs)。"""
    container = _mc_container()
    attrs = container.attrs
    state = attrs.get("State", {})
    host_cfg = attrs.get("HostConfig", {})
    running = bool(state.get("Running"))
    java_version = "Unknown"
    if running:
        started = state.get("StartedAt", "")
        if started not in _java_version_cache:
            try:
                first = _container_exec(container, ["java", "-version"]).splitlines()[0]
                _java_version_cache.clear()
                _java_version_cache[started] = first.replace('"', '').strip()
            except Exception:
                pass
        java_version = _java_version_cache.get(started, "Unknown")
    mem = host_cfg.get("Memory") or 0
    cpus = host_cfg.get("NanoCpus") or 0
    heap = _container_env(container).get("MAX_MEMORY", "")
    specs = {
        "ram": f"{mem / 1024 ** 3:.1f} GB" if mem else "不限",
        "jvm_heap": f"{heap} (-Xmx{heap})" if heap else "--",
        "cpu_threads": int(cpus / 1e9) if cpus else (os.cpu_count() or 0),
        "container": f"Docker {MC_CONTAINER}",
    }
    return ("Running" if running else "N/A"), java_version, specs


def mask_ip(ip: str) -> str:
    if not ip or ip == "Unknown":
        return ip
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.**.***"
    return ip


@router.get("/status")
def get_mc_status(user: dict = Depends(get_current_user_obj)):
    """
    取得 Minecraft 伺服器詳細狀態。
    包含連線狀態、設定規格、LAN/WAN 連線資訊。
    """
    online = _check_online()

    # 若伺服器在線，嘗試讀取運行資訊
    uptime_str = "N/A"
    java_version = "Unknown"
    specs = {
        "ram": "16 GB",
        "jvm_heap": "14 GB (-Xmx14G)",
        "cpu_threads": 8,
        "container": "Proxmox LXC #102",
    }
    if MC_CONTAINER:
        try:
            uptime_str, java_version, specs = _container_status()
        except Exception:
            specs = {"ram": "--", "jvm_heap": "--", "cpu_threads": 0, "container": f"Docker {MC_CONTAINER}"}
    elif online:
        try:
            # 讀取 screen session 是否存在
            out, _ = _ssh_exec(f"screen -list | grep {MC_SCREEN_NAME}")
            if MC_SCREEN_NAME in out:
                uptime_str = "Running"

            # 嘗試讀取 Java 版本
            jv_out, _ = _ssh_exec("java -version 2>&1 | head -n 1")
            if jv_out:
                java_version = jv_out.replace('"', '').strip()
        except Exception:
            pass

    # 取得公網 IP（由 system_status 的 ipify 結果快取比較穩定，這裡單獨嘗試）
    public_ip = "Unknown"
    try:
        import requests as req
        r = req.get("https://api.ipify.org?format=json", timeout=3)
        if r.status_code == 200:
            public_ip = r.json().get("ip", "Unknown")
    except Exception:
        pass

    is_admin = user.get("role") in ("admin", "Administrator")
    display_wan_ip = public_ip if is_admin else mask_ip(public_ip)
    display_address_wan = f"{display_wan_ip}:{MC_LXC_PORT}" if display_wan_ip != "Unknown" else "--"

    return {
        "online": online,
        "server": {
            "name": "Absolute-Axis MC",
            "version": "Minecraft Java Edition",
            "java_version": java_version,
            "uptime": uptime_str,
            "screen_session": MC_SCREEN_NAME,
        },
        "connection": {
            "lan_ip": MC_LXC_IP,
            "port": MC_LXC_PORT,
            "wan_ip": display_wan_ip,
            "address_lan": f"{MC_LXC_IP}:{MC_LXC_PORT}" if MC_LXC_IP else "--",
            "address_wan": display_address_wan,
            "address_wan_real": f"{public_ip}:{MC_LXC_PORT}" if public_ip != "Unknown" else "--",
            "address_ddns": f"{MC_PUBLIC_HOST}:{MC_LXC_PORT}" if MC_PUBLIC_HOST else "--"
        },
        "specs": specs,
    }

# Dynu DDNS 自動更新背景背景程序
import os
import time
import threading

def run_ddns_updater():
    last_ip = None
    dynu_user = os.getenv("DYNU_USER", "")
    dynu_pass = os.getenv("DYNU_PASS")
    dynu_host = os.getenv("DYNU_HOSTNAME", "")
    
    if not (dynu_pass and dynu_user and dynu_host):
        print("[DDNS] DYNU_USER / DYNU_PASS / DYNU_HOSTNAME not configured. Skipping background updates.")
        return
        
    print(f"[DDNS] Starting background DDNS updater for {dynu_host}")
    while True:
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=5)
            if r.status_code == 200:
                current_ip = r.json().get("ip")
                if current_ip and current_ip != last_ip:
                    # 更新 Dynu DNS IP 記錄
                    update_url = f"https://api.dynu.com/nic/update?hostname={dynu_host}&myip={current_ip}&username={dynu_user}&password={dynu_pass}"
                    resp = requests.get(update_url, timeout=5)
                    if resp.status_code == 200:
                        last_ip = current_ip
                        print(f"[DDNS] Successfully synchronized {dynu_host} to {current_ip}")
        except Exception as e:
            print(f"[DDNS] Synchronization failed: {e}")
        time.sleep(300)

if os.getenv("DYNU_PASS") and os.getenv("DYNU_USER") and os.getenv("DYNU_HOSTNAME"):
    threading.Thread(target=run_ddns_updater, daemon=True).start()



@router.post("/command")
def send_mc_command(req: MCCommandRequest, user: dict = Depends(get_current_user_obj)):
    """
    向 Minecraft 伺服器注入指令（管理員限定）。
    容器模式走容器內的 rcon-cli（會回傳伺服器的回應）；
    否則透過 SSH 連線至 LXC 容器，並使用 screen stuff 注入至伺服器控制台。
    決策：方案 B（全指令放行，管理員自行負責）。
    """
    # 管理員權限驗證
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員執行 MC 指令")

    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="指令不得為空")

    if MC_CONTAINER:
        rcon_command = command.lstrip("/").strip()  # RCON 指令不帶開頭的斜線
        if not rcon_command:
            raise HTTPException(status_code=400, detail="指令不得為空")
        try:
            out = _container_exec(_mc_container(), ["rcon-cli", rcon_command])
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"RCON 指令失敗（伺服器可能還在啟動）：{str(e)}")
        log_event(
            user["username"],
            f"MC_COMMAND: [{command}] -> container {MC_CONTAINER} | out={out[:100] if out else 'ok'}"
        )
        return {
            "status": "ok",
            "command": command,
            "sent_at": datetime.now().isoformat(),
            "response": out,
        }

    # 確保指令前有斜線（Minecraft 控制台指令可不加斜線，但加上以保持一致性）
    # 注意：screen stuff 注入的指令不需要加斜線，原始指令即可
    # 使用 printf 以精確控制換行，避免 shell 轉義問題
    safe_command = command.replace("'", "'\\''")  # 處理單引號轉義
    ssh_cmd = f"screen -S {MC_SCREEN_NAME} -X eval 'stuff \"{safe_command}\\n\"'"

    try:
        out, err = _ssh_exec(ssh_cmd)
        log_event(
            user["username"],
            f"MC_COMMAND: [{command}] -> LXC {MC_LXC_IP} | out={out[:100] if out else 'ok'}"
        )
        return {
            "status": "ok",
            "command": command,
            "sent_at": datetime.now().isoformat(),
            "ssh_response": out or "Command injected successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SSH 指令注入失敗：{str(e)}")


INFO_FILE = os.path.join(BASE_PATH, "app", "minecraft-info.json")
PACKS_DIR = os.path.join(BASE_PATH, "scratch", "minecraft_packs")
os.makedirs(PACKS_DIR, exist_ok=True)

def _load_info() -> dict:
    if os.path.exists(INFO_FILE):
        try:
            with open(INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "description": "這裡輸入模組包的簡介與說明...",
        "server_pack_name": "無",
        "client_pack_name": "無",
        "client_pack_size": 0,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def _save_info(info: dict):
    with open(INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=4, ensure_ascii=False)


class MCInfoUpdate(BaseModel):
    description: str


@router.get("/info")
def get_mc_info(user: dict = Depends(get_current_user_obj)):
    """取得模組包簡介與展示狀態"""
    info = _load_info()
    client_zip = os.path.join(BASE_PATH, "static", "minecraft-client-pack.zip")
    info["has_client_pack"] = os.path.exists(client_zip)
    return info


@router.post("/info")
def update_mc_info(req: MCInfoUpdate, user: dict = Depends(get_current_user_obj)):
    """編輯模組包簡介（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員修改模組包資訊")
        
    info = _load_info()
    info["description"] = req.description
    info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_info(info)
    
    log_event(user["username"], "MC_ADMIN: Updated modpack description")
    return {"status": "ok", "info": info}


@router.post("/upload-client")
async def upload_client_pack(file: UploadFile = File(...), user: dict = Depends(get_current_user_obj)):
    """上傳客戶端包（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員上傳模組包")
        
    client_zip_dir = os.path.join(BASE_PATH, "static")
    os.makedirs(client_zip_dir, exist_ok=True)
    target_path = os.path.join(client_zip_dir, "minecraft-client-pack.zip")
    
    try:
        with open(target_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunk
                if not chunk:
                    break
                buffer.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存客戶端包失敗: {str(e)}")
        
    info = _load_info()
    info["client_pack_name"] = file.filename
    info["client_pack_size"] = os.path.getsize(target_path)
    info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_info(info)
    
    log_event(user["username"], f"MC_ADMIN: Uploaded client pack {file.filename}")
    return {"status": "ok", "filename": file.filename}


# 模組包函式庫收的副檔名：一般伺服器包是 .zip；Modrinth 模組包是 .mrpack（也常被改名成 .zip）
PACK_EXTS = (".zip", ".mrpack")


def _is_pack_file(fname: str) -> bool:
    return fname.lower().endswith(PACK_EXTS)


# 各模組包世界資料存放根目錄（LXC 容器上）
WORLDS_BASE = "/root/minecraft_worlds"
# MC 的世界目錄名稱清單
WORLD_DIRS = ["world", "world_nether", "world_the_end", "DIM-1", "DIM1"]


def _pack_slug(pack_name: str) -> str:
    """從模組包檔名取得安全的目錄名稱（僅保留英數點底線減號，並附加 MD5 防止衝突與中文亂碼）"""
    import re
    import hashlib
    slug = pack_name.strip()
    for ext in PACK_EXTS:
        if slug.lower().endswith(ext):
            slug = slug[:-len(ext)]
            break
    safe_slug = re.sub(r'[^a-zA-Z0-9_\-\.]', '', slug)
    md5_hex = hashlib.md5(pack_name.encode('utf-8')).hexdigest()[:8]
    if not safe_slug:
        return f"world_{md5_hex}"
    return f"{safe_slug}_{md5_hex}"


def _ssh_save_world(client, pack_name: str):
    """
    自訂世界資料夾模式下，此處不做物理移動，世界資料夾直接存放在 /root/minecraft/world_{slug}。
    """
    pass


def _ssh_restore_world(client, pack_name: str):
    """
    世界資料夾過渡與相容：
    若舊有備份目錄下有世界，且新專屬世界目錄不存在，則過渡搬移。
    若 /root/minecraft/world 存在，且 /root/minecraft/world_{slug} 不存在，亦將其更名為新目錄。
    """
    if not pack_name or pack_name in ("無", ""):
        return
    slug = _pack_slug(pack_name)
    cmd = (
        f"if [ -d '{WORLDS_BASE}/{slug}' ] && [ ! -d '/root/minecraft/world_{slug}' ]; then "
        f"  mkdir -p '/root/minecraft/world_{slug}' && "
        f"  for d in {' '.join(WORLD_DIRS)}; do "
        f"    [ -d '{WORLDS_BASE}/{slug}'/$d ] && mv '{WORLDS_BASE}/{slug}'/$d '/root/minecraft/world_{slug}/' || true; "
        f"  done; "
        f"fi; "
        f"if [ -d '/root/minecraft/world' ] && [ ! -d '/root/minecraft/world_{slug}' ]; then "
        f"  mv '/root/minecraft/world' '/root/minecraft/world_{slug}'; "
        f"fi"
    )
    _, stdout, _ = client.exec_command(cmd)
    stdout.channel.recv_exit_status()


def _ssh_delete_world(client, pack_name: str):
    """刪除指定模組包的存檔地圖（讓下次進入時生成全新地圖）"""
    if not pack_name or pack_name in ("無", ""):
        return
    slug = _pack_slug(pack_name)
    # 同時清除舊備份與新的專屬世界目錄
    cmd = f"rm -rf '{WORLDS_BASE}/{slug}' '/root/minecraft/world_{slug}'"
    _, stdout, _ = client.exec_command(cmd)
    stdout.channel.recv_exit_status()


def _ssh_has_world(client, pack_name: str) -> bool:
    """偵測指定模組包是否有存過地圖"""
    if not pack_name or pack_name in ("無", ""):
        return False
    slug = _pack_slug(pack_name)
    # 同時檢查舊備份目錄與新專屬世界目錄
    cmd = (
        f"if [ -d '{WORLDS_BASE}/{slug}/world' ] || [ -d '/root/minecraft/world_{slug}' ]; then "
        f"  echo 'yes'; "
        f"else "
        f"  echo 'no'; "
        f"fi"
    )
    _, stdout, _ = client.exec_command(cmd)
    result = stdout.read().decode().strip()
    return result == "yes"


# ---------- 容器模式：模組包與世界 ----------
# 每個模組包的世界在停用時搬到這裡（資料目錄底下），切回來時再搬回去
WORLD_STORE = ".axis-worlds"
# 記錄資料目錄裡目前是哪個模組包（info.json 可能是舊的，不能拿來決定世界歸屬）
ACTIVE_MARKER = ".axis-active-pack"
_FORGE_LIB = re.compile(r"(?:^|/)libraries/net/minecraftforge/forge/(\d+(?:\.\d+)+)-[^/]+/")


def _read_marker() -> str:
    try:
        with open(os.path.join(MC_DATA_DIR, ACTIVE_MARKER), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _pack_info(zip_path: str) -> Tuple[str, str]:
    """
    看模組包是哪一種、給哪個 Minecraft 版本，回傳 (格式, 版本)：
    - "modrinth"：根目錄有 modrinth.index.json（模組由容器依清單下載），版本取 dependencies.minecraft
    - "generic"：一般伺服器包（直接解壓），版本從內附的 Forge 函式庫路徑判斷
    看不出版本時版本是空字串。
    """
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            if "modrinth.index.json" in names:
                try:
                    index = json.loads(z.read("modrinth.index.json"))
                    version = str((index.get("dependencies") or {}).get("minecraft", "")).strip()
                except (ValueError, AttributeError):
                    raise Exception("Modrinth 模組包的 modrinth.index.json 讀不懂")
                return "modrinth", version
            for name in names:
                m = _FORGE_LIB.search(name)
                if m:
                    return "generic", m.group(1)
    except (OSError, zipfile.BadZipFile):
        raise Exception("模組包不是有效的 zip／mrpack 檔")
    return "generic", ""


def _container_has_world(pack_name: str) -> bool:
    if not pack_name or pack_name in ("無", ""):
        return False
    return os.path.isdir(os.path.join(MC_DATA_DIR, WORLD_STORE, _pack_slug(pack_name)))


def _deploy_pack_to_container(local_zip_path: str, reset_world: bool = False):
    """
    容器模式的部署（每包獨立世界）：
    1. 檢查容器設定與模組包版本（不符就不動伺服器）
    2. 停止容器（Minecraft 會先存檔）
    3. 把目前的世界搬到 .axis-worlds/{目前包}
    4. 換掉容器的模組包檔：一般伺服器包是 GENERIC_PACK（啟動時解壓）；
       TYPE=MODRINTH 是 MODRINTH_MODPACK（啟動時依清單下載模組、安裝對應的 Forge／Fabric）。
       兩種都會在啟動時自動清掉舊包的檔案
    5. reset_world=True 就刪掉新包存過的世界；否則搬回來
    6. 啟動容器
    """
    new_pack_name = os.path.basename(local_zip_path)
    container = _mc_container()
    env = _container_env(container)

    modrinth_mode = env.get("TYPE", "").strip().upper() == "MODRINTH"
    pack_var, env_name = (("MODRINTH_MODPACK", "MC_MODRINTH_PACK=/data/modpack.mrpack") if modrinth_mode
                          else ("GENERIC_PACK", "MC_SERVER_PACK=/data/server.zip"))
    pack_in_container = env.get(pack_var, "").strip()
    level = env.get("LEVEL", "").strip()
    if not pack_in_container.startswith("/data/") or not level or "/" in level or level.startswith("."):
        raise Exception(
            f"容器沒有設定 {pack_var}（.env 的 {env_name}）或 LEVEL；"
            "請更新 .env／docker-compose.yml 後執行 docker compose up -d minecraft-server"
        )
    data_dir = os.path.realpath(MC_DATA_DIR)
    pack_target = os.path.realpath(os.path.join(data_dir, pack_in_container[len("/data/"):]))
    if not pack_target.startswith(data_dir + os.sep):
        raise Exception(f"{pack_var} 路徑不在資料目錄內")

    pack_format, have = _pack_info(local_zip_path)
    if pack_format == "modrinth" and not modrinth_mode:
        raise Exception(
            "這是 Modrinth 模組包（模組要依清單下載），容器目前設定為一般伺服器包；"
            "請把 .env 的 MC_TYPE 改成 MODRINTH、設定 MC_MODRINTH_PACK=/data/modpack.mrpack，"
            "再執行 docker compose up -d minecraft-server"
        )
    if pack_format != "modrinth" and modrinth_mode:
        raise Exception(
            "容器目前設定為 Modrinth 模式，這個檔案不是 Modrinth 模組包（沒有 modrinth.index.json）；"
            "要用一般伺服器包，請把 .env 的 MC_TYPE 改回 FORGE（或其他類型）並設定 MC_SERVER_PACK"
        )
    want = env.get("VERSION", "").strip()
    if have and want and want.upper() != "LATEST" and have != want:
        raise Exception(
            f"這個模組包是 Minecraft {have}，容器設定的是 {want}；"
            "請先改 .env 的 MC_VERSION／MC_FORGE_VERSION 並執行 docker compose up -d minecraft-server"
        )

    container.stop(timeout=120)

    store = os.path.join(data_dir, WORLD_STORE)
    os.makedirs(store, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    current = _read_marker()
    world_dir = os.path.join(data_dir, level)

    # 3. 目前的世界收起來；不知道是哪個包的世界就另外保留，不覆蓋、不刪除
    if os.path.isdir(world_dir):
        dest = os.path.join(store, _pack_slug(current) if current else f"unassigned_{stamp}")
        if os.path.exists(dest):
            os.rename(dest, f"{dest}.old-{stamp}")
        os.rename(world_dir, dest)

    # 4. 目前的 zip 若不是從函式庫複製來的（沒有標記），先收進函式庫，避免唯一的一份被蓋掉
    if os.path.isfile(pack_target) and not current:
        keep = os.path.join(PACKS_DIR, os.path.basename(pack_target))
        if os.path.exists(keep):
            keep = os.path.join(PACKS_DIR, f"{stamp}-{os.path.basename(pack_target)}")
        shutil.move(pack_target, keep)
    tmp = pack_target + ".axis-tmp"
    shutil.copyfile(local_zip_path, tmp)
    os.replace(tmp, pack_target)

    # 5. 新包的世界
    saved = os.path.join(store, _pack_slug(new_pack_name))
    if reset_world and os.path.isdir(saved):
        shutil.rmtree(saved)
    if os.path.isdir(saved):
        os.rename(saved, world_dir)

    with open(os.path.join(data_dir, ACTIVE_MARKER), "w", encoding="utf-8") as f:
        f.write(new_pack_name)

    container.start()


def _deploy_pack_to_lxc(
    local_zip_path: str,
    current_pack: str = "",
    reset_world: bool = False
):
    """
    共用部署函數（支援每包獨立世界）：
    1. 停止 MC
    2. 保存目前包的地圖 → WORLDS_BASE/{current_slug}/
    3. 清除 mods/config 等模組相關目錄
    4. SFTP 上傳並解壓新包
    5. 若 reset_world=True，刪除新包已存的地圖（讓 MC 重新生成）
    6. 還原新包的地圖（若存在） → /root/minecraft/
    7. 啟動 MC
    """
    if MC_CONTAINER:
        return _deploy_pack_to_container(local_zip_path, reset_world=reset_world)
    new_pack_name = os.path.basename(local_zip_path)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(MC_LXC_IP, username=MC_SSH_USER, password=MC_SSH_PASS, timeout=30)
    try:
        # 1. 停止 MC（等待服務完全停止）
        _, stdout_stop, _ = client.exec_command("systemctl stop minecraft && sleep 2")
        stdout_stop.channel.recv_exit_status()

        # 2. 保存目前包的地圖
        _ssh_save_world(client, current_pack)

        # 3. 清除舊模組/設定（world 已移走，這裡不會誤刪）
        clean_cmd = (
            "cd /root/minecraft && "
            "rm -rf mods config kubejs defaultconfigs modernfix "
            "libraries patchouli_books tlm_custom_pack"
        )
        _, stdout_clean, _ = client.exec_command(clean_cmd)
        stdout_clean.channel.recv_exit_status()

        # 4. SFTP 上傳並解壓新包
        remote_zip = "/root/minecraft_server_upload.zip"
        sftp = client.open_sftp()
        sftp.put(local_zip_path, remote_zip)
        sftp.close()
        extract_cmd = f"unzip -o {remote_zip} -d /root/minecraft > /dev/null 2>&1 && rm -f {remote_zip}"
        _, stdout_ext, _ = client.exec_command(extract_cmd)
        status = stdout_ext.channel.recv_exit_status()
        if status != 0:
            raise Exception(f"解壓縮模組包失敗，Exit Code: {status}")

        # 4.5 自動重整目錄結構，防範模組包帶有頂層/多層嵌套或中文編碼目錄
        restruct_cmd = (
            "MODS_PATH=$(find /root/minecraft -type d -name 'mods' | awk -F'/' '{ print NF, $0 }' | sort -n | cut -d' ' -f2- | head -n 1) && "
            "if [ -n \"$MODS_PATH\" ]; then "
            "  REAL_DIR=$(dirname \"$MODS_PATH\"); "
            "  if [ \"$REAL_DIR\" != \"/root/minecraft\" ]; then "
            "    find \"$REAL_DIR\" -maxdepth 1 -mindepth 1 -exec mv -t /root/minecraft/ {} +; "
            "    TEMP_TOP=$(echo \"$REAL_DIR\" | cut -d'/' -f4); "
            "    if [ -n \"$TEMP_TOP\" ] && [ \"$TEMP_TOP\" != \"minecraft\" ]; then "
            "      rm -rf \"/root/minecraft/$TEMP_TOP\"; "
            "    fi; "
            "  fi; "
            "fi"
        )
        _, stdout_restruct, _ = client.exec_command(restruct_cmd)
        stdout_restruct.channel.recv_exit_status()

        # 5. 若選擇重置地圖，刪除新包的存檔地圖
        if reset_world:
            _ssh_delete_world(client, new_pack_name)

        # 6. 還原新包的地圖（若存在）
        _ssh_restore_world(client, new_pack_name)

        # 6.5 修改 server.properties 的 level-name 指向專屬世界，並強制停用 Watchdog
        slug = _pack_slug(new_pack_name)
        prop_cmd = (
            f"python3 -c \""
            f"import re, os; "
            f"p = '/root/minecraft/server.properties'; "
            f"c = open(p).read() if os.path.exists(p) else ''; "
            f"c = re.sub(r'^level-name=.*', 'level-name=world_{slug}', c, flags=re.M) if 'level-name=' in c else c + '\\nlevel-name=world_{slug}\\n'; "
            f"c = re.sub(r'^max-tick-time=.*', 'max-tick-time=-1', c, flags=re.M) if 'max-tick-time=' in c else c + '\\nmax-tick-time=-1\\n'; "
            f"open(p, 'w').write(c)\""
        )
        _, stdout_prop, _ = client.exec_command(prop_cmd)
        stdout_prop.channel.recv_exit_status()

        # 6.6 動態探測模組版本並生成 run.sh
        gen_script = (
            "import os\n"
            "mods = os.listdir('/root/minecraft/mods') if os.path.exists('/root/minecraft/mods') else []\n"
            "is_21 = any('1.21' in m for m in mods)\n"
            "is_20 = any('1.20' in m for m in mods)\n"
            "run_path = '/root/minecraft/run.sh'\n"
            "if is_21 or (not is_20 and os.path.exists('/root/minecraft/libraries/net/neoforged/')):\n"
            "    neo_dir = '/root/minecraft/libraries/net/neoforged/neoforge'\n"
            "    neo_versions = os.listdir(neo_dir) if os.path.exists(neo_dir) else []\n"
            "    neo_ver = neo_versions[0] if neo_versions else '21.1.233'\n"
            "    cmd = f'java @user_jvm_args.txt -XX:+UnlockExperimentalVMOptions -XX:+UseZGC -XX:+ExplicitGCInvokesConcurrent -XX:+UseLargePages -Xss1M -XX:ConcGCThreads=4 -XX:ZAllocationSpikeTolerance=2 -XX:ZCollectionInterval=120 -Dfile.encoding=UTF-8 @libraries/net/neoforged/neoforge/{neo_ver}/unix_args.txt \"$@\"\\n'\n"
            "else:\n"
            "    forge_dir = '/root/minecraft/libraries/net/minecraftforge/forge'\n"
            "    versions = os.listdir(forge_dir) if os.path.exists(forge_dir) else []\n"
            "    ver = versions[0] if versions else '1.20.1-47.4.0'\n"
            "    cmd = f'java @user_jvm_args.txt @libraries/net/minecraftforge/forge/{ver}/unix_args.txt \"$@\"\\n'\n"
            "open(run_path, 'w').write('#!/usr/bin/env sh\\n' + cmd)\n"
            "os.chmod(run_path, 0o755)\n"
        )
        run_sh_cmd = (
            f"cat << 'EOF' > /tmp/gen_run.py\n"
            f"{gen_script}"
            f"EOF\n"
            f"python3 /tmp/gen_run.py && rm -f /tmp/gen_run.py"
        )
        _, stdout_run, _ = client.exec_command(run_sh_cmd)
        run_status = stdout_run.channel.recv_exit_status()
        if run_status != 0:
            raise Exception(f"生成 run.sh 啟動檔失敗，Exit Code: {run_status}")

        # 7. 啟動 MC
        _, stdout_start, _ = client.exec_command("systemctl start minecraft")
        stdout_start.channel.recv_exit_status()
    finally:
        client.close()


@router.post("/upload-server")
async def upload_server_pack(file: UploadFile = File(...), user: dict = Depends(get_current_user_obj)):
    """上傳伺服器包至函式庫並立即部署（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員上傳模組包")

    safe_filename = os.path.basename(file.filename)
    pack_path = os.path.join(PACKS_DIR, safe_filename)

    try:
        with open(pack_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)
    except Exception as e:
        if os.path.exists(pack_path):
            os.remove(pack_path)
        raise HTTPException(status_code=500, detail=f"儲存伺服器包失敗: {str(e)}")

    # 讀取目前啟用的包名稱，以便保存其世界
    info = _load_info()
    current_pack = info.get("active_pack", "") or info.get("server_pack_name", "")

    try:
        _deploy_pack_to_lxc(pack_path, current_pack=current_pack)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"部署伺服器包失敗: {str(e)}")

    info["server_pack_name"] = safe_filename
    info["active_pack"] = safe_filename
    info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_info(info)

    log_event(user["username"], f"MC_ADMIN: Uploaded and deployed server pack {safe_filename}")
    return {"status": "ok", "filename": safe_filename}


def _list_packs_container() -> dict:
    """容器模式的函式庫清單：啟用中的包以資料目錄的標記為準。"""
    active = _read_marker()
    level = ""
    try:
        level = _container_env(_mc_container()).get("LEVEL", "").strip()
    except HTTPException:
        pass
    live_world = bool(level) and os.path.isdir(os.path.join(MC_DATA_DIR, level))
    packs = []
    for fname in sorted(os.listdir(PACKS_DIR)):
        if _is_pack_file(fname):
            packs.append({
                "name": fname,
                "size_mb": round(os.path.getsize(os.path.join(PACKS_DIR, fname)) / 1024 / 1024, 1),
                "active": fname == active,
                "in_library": True,
                # 啟用中的包，世界就在資料目錄裡；其他包看 .axis-worlds
                "has_world": live_world if fname == active else _container_has_world(fname),
            })
    return {"packs": packs, "active_pack": active}


@router.get("/packs")
def list_packs(user: dict = Depends(get_current_user_obj)):
    """列出模組包函式庫中的所有 ZIP 檔（管理員限定），含每包是否有存檔地圖"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員查看模組包列表")

    info = _load_info()
    active = info.get("active_pack", "") or info.get("server_pack_name", "")

    # 透過 SSH 一次取得所有包的世界存檔狀態
    world_status: dict[str, bool] = {}
    if MC_CONTAINER:
        return _list_packs_container()
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(MC_LXC_IP, username=MC_SSH_USER, password=MC_SSH_PASS, timeout=8)
        # 同時取得舊備份目錄與新專屬世界目錄的名稱
        cmd = (
            f"ls {WORLDS_BASE}/ 2>/dev/null || echo ''; "
            f"find /root/minecraft/ -maxdepth 1 -type d -name 'world_*' -exec basename {{}} \\; 2>/dev/null || echo ''"
        )
        _, stdout, _ = client.exec_command(cmd)
        output_lines = stdout.read().decode().split()
        saved_slugs = set()
        for line in output_lines:
            line = line.strip()
            if line.startswith("world_"):
                saved_slugs.add(line[6:])  # 提取 'world_' 後的 slug
            elif line:
                saved_slugs.add(line)
        client.close()

        # 讀取函式庫目錄中的包，比對 slug 是否有存檔
        for fname in os.listdir(PACKS_DIR):
            if fname.lower().endswith(".zip"):
                slug = _pack_slug(fname)
                world_status[fname] = slug in saved_slugs
    except Exception:
        pass  # SSH 失敗時 has_world 預設 False

    packs = []
    library_names = set()
    for fname in sorted(os.listdir(PACKS_DIR)):
        if fname.lower().endswith(".zip"):
            fpath = os.path.join(PACKS_DIR, fname)
            size_mb = round(os.path.getsize(fpath) / 1024 / 1024, 1)
            packs.append({
                "name": fname,
                "size_mb": size_mb,
                "active": fname == active,
                "in_library": True,
                "has_world": world_status.get(fname, False),
            })
            library_names.add(fname)

    # 若目前啟用的包不在函式庫目錄（舊版上傳，未保留），插入虛擬條目
    if active and active not in library_names and active not in ("無", ""):
        packs.insert(0, {
            "name": active,
            "size_mb": None,
            "active": True,
            "in_library": False,
            "has_world": False,
        })

    return {"packs": packs, "active_pack": active}


class SwitchPackRequest(BaseModel):
    pack_name: str
    reset_world: bool = False


@router.post("/switch-pack")
def switch_pack(req: SwitchPackRequest, user: dict = Depends(get_current_user_obj)):
    """從函式庫切換並部署指定模組包（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員切換模組包")

    safe_name = os.path.basename(req.pack_name)
    pack_path = os.path.join(PACKS_DIR, safe_name)
    if not os.path.exists(pack_path):
        raise HTTPException(status_code=404, detail=f"找不到模組包：{safe_name}")

    # 讀取目前啟用的包，以便切換時保存其地圖
    info = _load_info()
    current_pack = info.get("active_pack", "") or info.get("server_pack_name", "")

    try:
        _deploy_pack_to_lxc(pack_path, current_pack=current_pack, reset_world=req.reset_world)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切換模組包失敗: {str(e)}")

    info["server_pack_name"] = safe_name
    info["active_pack"] = safe_name
    info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_info(info)

    world_note = "（已重置地圖）" if req.reset_world else "（已還原該包地圖）"
    log_event(user["username"], f"MC_ADMIN: Switched server pack to {safe_name}{world_note}")
    return {"status": "ok", "active_pack": safe_name, "world_reset": req.reset_world}


@router.delete("/packs/{pack_name}")
def delete_pack(pack_name: str, user: dict = Depends(get_current_user_obj)):
    """從函式庫刪除指定模組包（管理員限定，不可刪除目前啟用的包）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員刪除模組包")

    safe_name = os.path.basename(pack_name)
    pack_path = os.path.join(PACKS_DIR, safe_name)
    if not os.path.exists(pack_path):
        raise HTTPException(status_code=404, detail=f"找不到模組包：{safe_name}")

    info = _load_info()
    if (_read_marker() if MC_CONTAINER else info.get("active_pack")) == safe_name:
        raise HTTPException(status_code=400, detail="無法刪除目前正在使用的模組包，請先切換至其他包")

    os.remove(pack_path)
    log_event(user["username"], f"MC_ADMIN: Deleted pack {safe_name} from library")
    return {"status": "ok"}


@router.post("/uninstall-server")
def uninstall_server_pack(user: dict = Depends(get_current_user_obj)):
    """卸載伺服器模組包（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員卸載模組包")
    if MC_CONTAINER:
        raise HTTPException(
            status_code=400,
            detail="容器模式不支援卸載（容器一定要有伺服器包才能啟動）；請改切換到其他模組包，或到虛擬化中心停止容器",
        )

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(MC_LXC_IP, username=MC_SSH_USER, password=MC_SSH_PASS, timeout=15)
        _, stdout_stop, _ = client.exec_command("systemctl stop minecraft && sleep 2")
        stdout_stop.channel.recv_exit_status()
        uninstall_cmd = (
            "cd /root/minecraft && "
            "rm -rf mods config kubejs defaultconfigs modernfix libraries patchouli_books tlm_custom_pack"
        )
        _, stdout_rm, _ = client.exec_command(uninstall_cmd)
        stdout_rm.channel.recv_exit_status()
        _, stdout_start, _ = client.exec_command("systemctl start minecraft")
        stdout_start.channel.recv_exit_status()
        client.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"卸載伺服器包失敗: {str(e)}")

    info = _load_info()
    info["server_pack_name"] = "無"
    info["active_pack"] = ""
    info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_info(info)

    log_event(user["username"], "MC_ADMIN: Uninstalled server pack")
    return {"status": "ok"}
