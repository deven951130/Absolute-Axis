import socket
import paramiko
import os
import json
import requests
from typing import Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from datetime import datetime

from app.models import MCCommandRequest
from app.utils import get_current_user_obj, log_event
from app.config import BASE_PATH

router = APIRouter(prefix="/api/minecraft", tags=["minecraft"])

# LXC 容器連線設定
MC_LXC_IP = "192.168.0.130"
MC_LXC_PORT = 25565
MC_SSH_USER = "root"
MC_SSH_PASS = "951130"
MC_SCREEN_NAME = "mc"


def _check_online() -> bool:
    """快速 TCP 探測 Minecraft 是否存活。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((MC_LXC_IP, MC_LXC_PORT)) == 0
    except Exception:
        return False


def _ssh_exec(command: str) -> Tuple[str, str]:
    """透過 SSH 在 LXC 容器中執行指令，回傳 (stdout, stderr)。"""
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
    if online:
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
            "address_lan": f"{MC_LXC_IP}:{MC_LXC_PORT}",
            "address_wan": display_address_wan,
            "address_wan_real": f"{public_ip}:{MC_LXC_PORT}" if public_ip != "Unknown" else "--",
            "address_ddns": f"absoluteaxis.dpdns.org:{MC_LXC_PORT}"
        },
        "specs": {
            "ram": "16 GB",
            "jvm_heap": "14 GB (-Xmx14G)",
            "cpu_threads": 8,
            "container": "Proxmox LXC #102",
        },
    }

# Dynu DDNS 自動更新背景背景程序
import os
import time
import threading

def run_ddns_updater():
    last_ip = None
    dynu_user = os.getenv("DYNU_USER", "deven951130")
    dynu_pass = os.getenv("DYNU_PASS")
    
    if not dynu_pass:
        print("[DDNS] DYNU_PASS not configured. Skipping background updates.")
        return
        
    print("[DDNS] Starting background DDNS updater for absoluteaxis.dpdns.org")
    while True:
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=5)
            if r.status_code == 200:
                current_ip = r.json().get("ip")
                if current_ip and current_ip != last_ip:
                    # 更新 Dynu DNS IP 記錄
                    update_url = f"https://api.dynu.com/nic/update?hostname=absoluteaxis.dpdns.org&myip={current_ip}&username={dynu_user}&password={dynu_pass}"
                    resp = requests.get(update_url, timeout=5)
                    if resp.status_code == 200:
                        last_ip = current_ip
                        print(f"[DDNS] Successfully synchronized absoluteaxis.dpdns.org to {current_ip}")
        except Exception as e:
            print(f"[DDNS] Synchronization failed: {e}")
        time.sleep(300)

if os.getenv("DYNU_PASS"):
    threading.Thread(target=run_ddns_updater, daemon=True).start()



@router.post("/command")
def send_mc_command(req: MCCommandRequest, user: dict = Depends(get_current_user_obj)):
    """
    向 Minecraft 伺服器注入指令（管理員限定）。
    透過 SSH 連線至 LXC 容器，並使用 screen stuff 注入至伺服器控制台。
    決策：方案 B（全指令放行，管理員自行負責）。
    """
    # 管理員權限驗證
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員執行 MC 指令")

    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="指令不得為空")

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


def _deploy_pack_to_lxc(local_zip_path: str, reset_world: bool = False):
    """
    共用部署函數：停止 MC → SFTP 上傳 → 清除舊模組 → 解壓 → [可選] 重置地圖 → 啟動 MC。
    所有步驟均等待完成，確保重啟時序正確。
    reset_world=True 時會刪除 world/ world_nether/ world_the_end/ 讓 MC 生成全新地圖。
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(MC_LXC_IP, username=MC_SSH_USER, password=MC_SSH_PASS, timeout=30)
    try:
        # 1. 停止 MC（等待服務完全停止）
        _, stdout_stop, _ = client.exec_command("systemctl stop minecraft && sleep 2")
        stdout_stop.channel.recv_exit_status()

        # 2. SFTP 上傳 ZIP 至 LXC
        remote_zip = "/root/minecraft_server_upload.zip"
        sftp = client.open_sftp()
        sftp.put(local_zip_path, remote_zip)
        sftp.close()

        # 3. 清除舊模組/設定（保留 world/存檔/properties）
        clean_cmd = (
            "cd /root/minecraft && "
            "rm -rf mods config kubejs defaultconfigs modernfix "
            "libraries patchouli_books tlm_custom_pack"
        )
        _, stdout_clean, _ = client.exec_command(clean_cmd)
        stdout_clean.channel.recv_exit_status()

        # 4. 解壓新包
        extract_cmd = f"unzip -o {remote_zip} -d /root/minecraft && rm -f {remote_zip}"
        _, stdout_ext, stderr_ext = client.exec_command(extract_cmd)
        stdout_ext.channel.recv_exit_status()

        # 4.5 若選擇重置地圖，删除全部世界資料廞
        if reset_world:
            reset_cmd = (
                "rm -rf /root/minecraft/world "
                "/root/minecraft/world_nether "
                "/root/minecraft/world_the_end "
                "/root/minecraft/DIM-1 "
                "/root/minecraft/DIM1"
            )
            _, stdout_reset, _ = client.exec_command(reset_cmd)
            stdout_reset.channel.recv_exit_status()

        # 5. 啟動 MC（等待服務啟動完成）
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

    # 存到函式庫目錄（永久保存，供日後切換使用）
    safe_filename = os.path.basename(file.filename)
    pack_path = os.path.join(PACKS_DIR, safe_filename)

    try:
        with open(pack_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunk
                if not chunk:
                    break
                buffer.write(chunk)
    except Exception as e:
        if os.path.exists(pack_path):
            os.remove(pack_path)
        raise HTTPException(status_code=500, detail=f"儲存伺服器包失敗: {str(e)}")

    try:
        _deploy_pack_to_lxc(pack_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"部署伺服器包失敗: {str(e)}")

    info = _load_info()
    info["server_pack_name"] = safe_filename
    info["active_pack"] = safe_filename
    info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_info(info)

    log_event(user["username"], f"MC_ADMIN: Uploaded and deployed server pack {safe_filename}")
    return {"status": "ok", "filename": safe_filename}


@router.get("/packs")
def list_packs(user: dict = Depends(get_current_user_obj)):
    """列出模組包函式庫中的所有 ZIP 檔（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員查看模組包列表")

    info = _load_info()
    active = info.get("active_pack", "") or info.get("server_pack_name", "")

    # 讀取函式庫目錄中所有 ZIP
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
            })
            library_names.add(fname)

    # 若目前啟用的包不在函式庫目錄（舊版上傳，未保留），插入虛擬條目顯示在頂部
    if active and active not in library_names and active not in ("無", ""):
        packs.insert(0, {
            "name": active,
            "size_mb": None,
            "active": True,
            "in_library": False,
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

    try:
        _deploy_pack_to_lxc(pack_path, reset_world=req.reset_world)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切換模組包失敗: {str(e)}")

    info = _load_info()
    info["server_pack_name"] = safe_name
    info["active_pack"] = safe_name
    info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_info(info)

    world_note = "（已重置地圖）" if req.reset_world else ""
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
    if info.get("active_pack") == safe_name:
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
