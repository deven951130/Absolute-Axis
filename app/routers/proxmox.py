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
            timeout=10
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
