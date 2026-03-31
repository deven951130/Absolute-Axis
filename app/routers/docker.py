import json
import subprocess
from fastapi import APIRouter, Depends

from app.models import DockerControlRequest, DeployVMRequest
from app.utils import get_current_user_obj, log_event
import socket

router = APIRouter(prefix="/api/docker", tags=["docker"])

@router.get("/containers")
def list_containers(user: dict = Depends(get_current_user_obj)):
    try:
        out = subprocess.check_output(["docker", "ps", "-a", "--format", "{{json .}}"]).decode()
        containers = [json.loads(l) for l in out.strip().split('\n') if l]
        # Attach our custom VNC port parsing for the UI
        for c in containers:
            ports = c.get("Ports", "")
            if "8006->8006" in ports or "->8006" in ports:
                c["vnc_port"] = ports.split("->8006")[0].split(":")[-1]
            elif "->3000" in ports:
                c["vnc_port"] = ports.split("->3000")[0].split(":")[-1]
            elif "->6080" in ports: # docker-android / osx
                c["vnc_port"] = ports.split("->6080")[0].split(":")[-1]
        return containers
    except: 
        return []

@router.post("/control")
def control_docker(req: DockerControlRequest, user: dict = Depends(get_current_user_obj)):
    subprocess.run(["docker", req.action, req.container_id])
    log_event(user["username"], f"Virtual Center: {req.action.upper()} container {req.container_id[:8]}")
    return {"status": "ok"}

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@router.post("/deploy")
def deploy_vm(req: DeployVMRequest, user: dict = Depends(get_current_user_obj)):
    # 支援的 OS 作業系統對照表
    os_map = {
        "win11": {"type": "dockurr", "image": "dockurr/windows", "env_ver": "win11", "internal_port": 8006},
        "win10": {"type": "dockurr", "image": "dockurr/windows", "env_ver": "win10", "internal_port": 8006},
        "win-server": {"type": "dockurr", "image": "dockurr/windows", "env_ver": "win2022", "internal_port": 8006},
        "ubuntu": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:ubuntu-kde", "internal_port": 3000},
        "debian": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:debian-kde", "internal_port": 3000},
        "arch": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:arch-kde", "internal_port": 3000},
        "kali": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:kali-kde", "internal_port": 3000},
        "macos": {"type": "sickcodes", "image": "sickcodes/docker-osx:auto", "internal_port": 6080}, # sickcodes has novnc on 6080 for web access? Actually VNC is 5999, but we try to map if available. We will map 50922 and 5999.
        "android": {"type": "android", "image": "budtmo/docker-android:emulator_11.0", "internal_port": 6080}
    }

    if req.os_internal_name not in os_map:
        return {"status": "error", "message": "Unknown OS"}

    cfg = os_map[req.os_internal_name]
    vps_port = get_free_port()
    name = req.container_name.replace(" ", "_").lower()
    
    cmd = ["docker", "run", "-d", "--name", name, "--cap-add=NET_ADMIN", "--device=/dev/kvm", "--privileged"]

    if cfg["type"] == "dockurr":
        cmd.extend([
            "-e", f"VERSION={cfg['env_ver']}",
            "-e", f"CPU_CORES={req.cpu_cores}",
            "-e", f"RAM_SIZE={req.ram_gb}G",
            "-p", f"{vps_port}:8006",
            "-p", f"{get_free_port()}:3389/tcp",
            "-p", f"{get_free_port()}:3389/udp",
            cfg["image"]
        ])
    elif cfg["type"] == "webtop":
        cmd.extend([
            "-e", "PUID=1000", "-e", "PGID=1000", "-e", "TZ=Asia/Taipei",
            "--shm-size", f"{req.ram_gb}gb",
            "-p", f"{vps_port}:3000",
            cfg["image"]
        ])
    elif cfg["type"] == "android":
        cmd.extend([
            "-e", "EMULATOR_DEVICE=Samsung Galaxy S10", 
            "-e", "WEB_VNC=true",
            "-p", f"{vps_port}:6080",
            cfg["image"]
        ])
    else: # macos
        cmd.extend([
            "-e", f"RAM={req.ram_gb}",
            "-e", f"CORES={req.cpu_cores}",
            "-p", f"{get_free_port()}:50922", 
            "-p", f"{get_free_port()}:10022",
            "-e", "GENERATE_UNIQUE=true",
            cfg["image"]
        ])

    subprocess.Popen(cmd) # async start as it might take time
    log_event(user["username"], f"Deployed robust OS Instance: {req.container_name} ({req.os_internal_name.upper()}) on port {vps_port}")
    
    return {"status": "ok", "message": "Deployment initiated! It may take some time to download and boot the OS image."}
