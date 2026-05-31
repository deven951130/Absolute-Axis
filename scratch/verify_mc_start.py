import paramiko

def verify_mc():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== Checking systemd service status ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- systemctl status minecraft.service")
        print(stdout.read().decode())
        
        print("=== Tail of Minecraft logs ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- tail -n 40 /root/minecraft/logs/latest.log")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    verify_mc()
