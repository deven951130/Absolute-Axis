import paramiko
import time

def hard_reboot_proxmox():
    px_ip = '192.168.0.138'
    px_user = 'root'
    px_pass = 'deven951130'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Connecting to Proxmox Host...")
        client.connect(px_ip, username=px_user, password=px_pass, timeout=10)
        
        print("FORCING RESET of VM 100 (Absolute-Axis Main)...")
        # 使用 qm reset 進行硬重啟
        client.exec_command('qm reset 100')
        
        print("Reset signal sent. Waiting 60 seconds for system cold boot...")
        time.sleep(60)
        
        print("System should be coming back online.")
    except Exception as e:
        print(f"Error on Proxmox: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    hard_reboot_proxmox()
