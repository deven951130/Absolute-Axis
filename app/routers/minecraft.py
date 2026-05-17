import socket
import paramiko
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime

from app.models import MCCommandRequest
from app.utils import get_current_user_obj, log_event

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


def _ssh_exec(command: str) -> tuple[str, str]:
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
            "wan_ip": public_ip,
            "address_lan": f"{MC_LXC_IP}:{MC_LXC_PORT}",
            "address_wan": f"{public_ip}:{MC_LXC_PORT}",
        },
        "specs": {
            "ram": "16 GB",
            "jvm_heap": "14 GB (-Xmx14G)",
            "cpu_threads": 8,
            "container": "Proxmox LXC #102",
        },
    }


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
