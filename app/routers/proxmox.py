from fastapi import APIRouter, Depends, HTTPException
from proxmoxer import ProxmoxAPI
from app.config import PVE_HOST, PVE_USER, PVE_PASS
from app.utils import get_current_user_obj
import urllib3

# Disable SSL warnings for internal PVE IP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

router = APIRouter(prefix="/api/proxmox", tags=["proxmox"])

def get_pve_client():
    try:
        proxmox = ProxmoxAPI(
            PVE_HOST, 
            user=PVE_USER, 
            password=PVE_PASS, 
            verify_ssl=False,
            timeout=60
        )
        return proxmox
    except Exception as e:
        print(f"PVE Connection Error: {e}")
        return None

@router.get("/status")
def get_pve_status(user: dict = Depends(get_current_user_obj)):
    pve = get_pve_client()
    if not pve:
        raise HTTPException(status_code=500, detail="Could not connect to Proxmox host.")
    
    try:
        # Get nodes list
        nodes = pve.nodes.get()
        res_nodes = []
        for node in nodes:
            name = node['node']
            # Get specific node status
            status = pve.nodes(name).status.get()
            res_nodes.append({
                "name": name,
                "status": node['status'],
                "cpu": round(status.get('cpu', 0) * 100, 1),
                "memory": {
                    "used": status.get('memory', {}).get('used', 0),
                    "total": status.get('memory', {}).get('total', 0),
                    "percent": round((status.get('memory', {}).get('used', 0) / status.get('memory', {}).get('total', 0) * 100), 1) if status.get('memory', {}).get('total', 0) > 0 else 0
                },
                "uptime": status.get('uptime', 0)
            })
        return res_nodes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vms")
def list_pve_vms(user: dict = Depends(get_current_user_obj)):
    pve = get_pve_client()
    if not pve:
        return []
    
    try:
        vms = []
        nodes = pve.nodes.get()
        for node in nodes:
            node_name = node['node']
            # QEMU VMs
            qemu = pve.nodes(node_name).qemu.get()
            for v in qemu:
                vms.append({
                    "id": v['vmid'],
                    "name": v['name'],
                    "type": "qemu",
                    "status": v['status'],
                    "node": node_name,
                    "cpu": round(v.get('cpus', 0), 1),
                    "mem": round(v.get('maxmem', 0) / (1024**3), 1)
                })
            # LXC Containers
            lxc = pve.nodes(node_name).lxc.get()
            for v in lxc:
                vms.append({
                    "id": v['vmid'],
                    "name": v['name'],
                    "type": "lxc",
                    "status": v['status'],
                    "node": node_name,
                    "cpu": round(v.get('cpus', 0), 1),
                    "mem": round(v.get('maxmem', 0) / (1024**3), 1)
                })
        return vms
    except Exception as e:
        print(f"PVE VM List Error: {e}")
        return []
@router.post("/vm/action")
def vm_action(vmid: int, node: str, action: str, vm_type: str = "qemu", user: dict = Depends(get_current_user_obj)):
    pve = get_pve_client()
    if not pve:
        raise HTTPException(status_code=500, detail="PVE Connection Error")
    
    try:
        if vm_type == "qemu":
            target = pve.nodes(node).qemu(vmid).status
        else:
            target = pve.nodes(node).lxc(vmid).status
            
        if action == "start":
            target.start.post()
        elif action == "stop":
            target.stop.post()
        elif action == "shutdown":
            target.shutdown.post()
        elif action == "reboot":
            target.reboot.post()
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        return {"status": "ok", "message": f"Action {action} sent to VM {vmid}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deploy")
def deploy_vm(os_type: str, user: dict = Depends(get_current_user_obj)):
    import paramiko
    import time
    
    # Recommended Specs
    specs = {
        "windows": {"name": "Win11-Quick", "cores": 4, "memory": 8192, "disk": 64, "iso": "win11.iso"},
        "ubuntu": {"name": "Ubuntu-24.04", "cores": 2, "memory": 4096, "disk": 20, "iso": "ubuntu-24.04.4-live-server-amd64.iso"},
        "kali": {"name": "Kali-Linux", "cores": 2, "memory": 4096, "disk": 40, "iso": "kali.iso"},
        "macos": {"name": "macOS-Sequoia", "cores": 4, "memory": 8192, "disk": 128, "iso": "macos.iso"}
    }
    
    config = specs.get(os_type.lower())
    if not config:
        raise HTTPException(status_code=400, detail="Unsupported OS type")
        
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # Use local IP for speed
        client.connect("192.168.0.138", username="root", password=PVE_PASS, timeout=15)
        
        # 1. Get next VMID
        stdin, stdout, stderr = client.exec_command("pvesh get /cluster/nextid")
        vmid = stdout.read().decode().strip()
        
        # 2. qm create
        cmd = f"qm create {vmid} --name {config['name']} --cores {config['cores']} --memory {config['memory']} --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci"
        client.exec_command(cmd)
        time.sleep(1)
        
        # 3. qm set (Disk & ISO)
        disk_cmd = f"qm set {vmid} --scsi0 Fast-Storage:{config['disk']}"
        client.exec_command(disk_cmd)
        
        iso_cmd = f"qm set {vmid} --ide2 local:iso/{config['iso']},media=cdrom"
        client.exec_command(iso_cmd)
        
        # 4. OS Type
        ostype = "l26" if os_type != "windows" else "win11"
        client.exec_command(f"qm set {vmid} --ostype {ostype}")
        
        client.close()
        return {
            "status": "ok", 
            "vmid": vmid, 
            "message": f"Successfully initialized {config['name']} via Direct Command. Please check ISO {config['iso']}."
        }
    except Exception as e:
        if client: client.close()
        raise HTTPException(status_code=500, detail=f"SSH Deploy Error: {str(e)}")
