import paramiko
import time

def start_mc():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("[*] Resetting failed status for minecraft.service...")
        client.exec_command("pct exec 102 -- systemctl reset-failed minecraft.service")
        
        print("[*] Starting minecraft.service...")
        client.exec_command("pct exec 102 -- systemctl start minecraft.service")
        
        print("[*] Waiting 5 seconds for initialization...")
        time.sleep(5)
        
        print("=== Minecraft service status ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- systemctl status minecraft.service")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    start_mc()
