import urllib3
import docker
import socket
from fastapi import APIRouter, Depends, HTTPException
from app.models import DockerControlRequest, DeployVMRequest
from app.utils import get_current_user_obj, log_event

# Hide SSL warnings if Docker connects over unverified HTTPS sometimes
urllib3.disable_warnings()

try:
    client = docker.from_env()
except Exception:
    client = None

router = APIRouter(prefix="/api/docker", tags=["docker"])

@router.get("/containers")
def list_containers(user: dict = Depends(get_current_user_obj)):
    if not client: return []
    try:
        res = []
        for c in client.containers.list(all=True):
            # parse ports to mimic original format for UI
            ports_str = ""
            vnc_port = None
            if c.ports:
                for int_p, ext_ps in c.ports.items():
                    if ext_ps:
                        host_p = ext_ps[0].get('HostPort', '')
                        ports_str += f"{host_p}->{int_p.split('/')[0]} "
                        if "8006" in int_p or "3000" in int_p or "6080" in int_p:
                            vnc_port = host_p
                            
            res.append({
                "ID": c.short_id,
                "Names": c.name,
                "Image": c.image.tags[0] if c.image.tags else c.image.id[:12],
                "State": c.status,
                "Status": c.status.upper(),
                "Ports": ports_str.strip(),
                "vnc_port": vnc_port
            })
        return res
    except Exception as e:
        print(f"Docker SDK error: {e}")
        return []

@router.post("/control")
def control_docker(req: DockerControlRequest, user: dict = Depends(get_current_user_obj)):
    if not client: raise HTTPException(status_code=500, detail="Docker SDK not connected.")
    try:
        container = client.containers.get(req.container_id)
        if req.action == "start": container.start()
        elif req.action == "stop": container.stop()
        elif req.action == "restart": container.restart()
        elif req.action == "rm": container.remove(force=True)
        else:
            raise HTTPException(status_code=400, detail="Unknown action")
            
        log_event(user["username"], f"Virtual Center: {req.action.upper()} (SDK) container {req.container_id[:8]}")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@router.post("/deploy")
def deploy_vm(req: DeployVMRequest, user: dict = Depends(get_current_user_obj)):
    if not client: raise HTTPException(status_code=500, detail="Docker SDK not connected.")
    
    os_map = {
        "win11": {"type": "dockurr", "image": "dockurr/windows", "env_ver": "win11", "internal_port": 8006},
        "win10": {"type": "dockurr", "image": "dockurr/windows", "env_ver": "win10", "internal_port": 8006},
        "win-server": {"type": "dockurr", "image": "dockurr/windows", "env_ver": "win2022", "internal_port": 8006},
        "ubuntu": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:ubuntu-kde", "internal_port": 3000},
        "debian": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:debian-kde", "internal_port": 3000},
        "arch": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:arch-kde", "internal_port": 3000},
        "kali": {"type": "webtop", "image": "lscr.io/linuxserver/webtop:kali-kde", "internal_port": 3000},
        "macos": {"type": "sickcodes", "image": "sickcodes/docker-osx:auto", "internal_port": 6080},
        "android": {"type": "android", "image": "budtmo/docker-android:emulator_11.0", "internal_port": 6080}
    }

    if req.os_internal_name not in os_map:
        return {"status": "error", "message": "Unknown OS"}

    cfg = os_map[req.os_internal_name]
    vps_port = str(get_free_port())
    name = req.container_name.replace(" ", "_").lower()
    
    env_vars = {}
    ports_map = {}
    
    if cfg["type"] == "dockurr":
        env_vars = {"VERSION": cfg['env_ver'], "CPU_CORES": str(req.cpu_cores), "RAM_SIZE": f"{req.ram_gb}G"}
        ports_map = {"8006/tcp": vps_port, "3389/tcp": str(get_free_port()), "3389/udp": str(get_free_port())}
    elif cfg["type"] == "webtop":
        env_vars = {"PUID": "1000", "PGID": "1000", "TZ": "Asia/Taipei"}
        ports_map = {"3000/tcp": vps_port}
    elif cfg["type"] == "android":
        env_vars = {"EMULATOR_DEVICE": "Samsung Galaxy S10", "WEB_VNC": "true"}
        ports_map = {"6080/tcp": vps_port}
    elif cfg["type"] == "sickcodes":
        env_vars = {"RAM": str(req.ram_gb), "CORES": str(req.cpu_cores), "GENERATE_UNIQUE": "true"}
        ports_map = {"50922/tcp": str(get_free_port()), "10022/tcp": str(get_free_port())}
        
    try:
        client.containers.run(
            cfg["image"],
            detach=True,
            name=name,
            cap_add=["NET_ADMIN"],
            devices=["/dev/kvm:/dev/kvm"],
            privileged=True,
            environment=env_vars,
            ports=ports_map,
            shm_size=f"{req.ram_gb}G" if cfg["type"] == "webtop" else None
        )
        log_event(user["username"], f"Deployed robust OS Instance: {req.container_name} ({req.os_internal_name.upper()}) on port {vps_port} via SDK")
        return {"status": "ok", "message": "Deployment initiated via SDK! It may take some time to download and boot."}
    except Exception as e:
        log_event(user["username"], f"Deployment Error: {str(e)[:50]}")
        raise HTTPException(status_code=500, detail=str(e))
