import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import paramiko
from proxmoxer import ProxmoxAPI

PVE_IP = '192.168.0.138'
PVE_USER_SSH = 'root'
PVE_PASS = 'deven951130'
PVE_USER_API = 'root@pam'
VMID = '102'

def try_api_stop():
    try:
        proxmox = ProxmoxAPI(
            PVE_IP, 
            user=PVE_USER_API, 
            password=PVE_PASS, 
            verify_ssl=False,
            timeout=3
        )
        # 取得節點名稱
        nodes = proxmox.nodes.get()
        if not nodes:
            return False
        node_name = nodes[0]['node']
        
        # 檢查 102 容器狀態
        lxc = proxmox.nodes(node_name).lxc(VMID).status.current.get()
        print(f"[API] Found LXC {VMID}, status: {lxc.get('status')}")
        
        # 停止容器
        print(f"[API] Sending stop command to LXC {VMID}...")
        proxmox.nodes(node_name).lxc(VMID).status.stop.post()
        
        # 修改 config 取消 onboot
        print(f"[API] Disabling onboot for LXC {VMID}...")
        proxmox.nodes(node_name).lxc(VMID).config.put(onboot=0)
        print("[API] SUCCESS! Container stopped and auto-boot disabled.")
        return True
    except Exception as e:
        print(f"[API Attempt Failed]: {e}")
        return False

def try_ssh_stop():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"[SSH] Attempting connection to {PVE_IP}...")
        client.connect(PVE_IP, username=PVE_USER_SSH, password=PVE_PASS, timeout=3)
        print("[SSH] SUCCESS: Connected to PVE host via SSH!")
        
        # 執行停止容器與停用自啟動
        print(f"[SSH] Executing: pct stop {VMID}...")
        stdin, stdout, stderr = client.exec_command(f"pct stop {VMID}")
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        print(f"[SSH] pct stop stdout: {out}")
        if err:
            print(f"[SSH] pct stop stderr: {err}")
            
        print(f"[SSH] Executing: pct set {VMID} -onboot 0...")
        stdin, stdout, stderr = client.exec_command(f"pct set {VMID} -onboot 0")
        print(f"[SSH] pct set stdout: {stdout.read().decode().strip()}")
        
        print("[SSH] SUCCESS! Container stopped and auto-boot disabled.")
        return True
    except Exception as e:
        print(f"[SSH Attempt Failed]: {e}")
        return False
    finally:
        client.close()

def main():
    print("==================================================")
    print("PVE Boot Intercept Tool (LXC 102 Watchdog Rescue)")
    print("==================================================")
    print("Please force reset/power cycle your physical PVE server now.")
    print("This script will continuously poll and intercept the system")
    print("before the watchdog lockup occurs (within the first 2 minutes).")
    print("Press Ctrl+C to stop.")
    print("==================================================")
    
    attempt = 1
    while True:
        print(f"\n[Attempt #{attempt}] Checking connectivity...")
        # 嘗試 API 通道
        api_success = try_api_stop()
        if api_success:
            print("\nRescue completed successfully via API!")
            break
            
        # 嘗試 SSH 通道
        ssh_success = try_ssh_stop()
        if ssh_success:
            print("\nRescue completed successfully via SSH!")
            break
            
        attempt += 1
        time.sleep(1)

if __name__ == '__main__':
    main()
