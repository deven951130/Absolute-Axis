import paramiko
import time

def verify_mc_port():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== Checking open ports in LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ss -tuln")
        print(stdout.read().decode())
        
        print("=== Last 30 lines of Minecraft logs ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- tail -n 30 /root/minecraft/logs/latest.log")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    verify_mc_port()
