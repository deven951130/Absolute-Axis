import paramiko

def check_zip_structure():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== Checking zip structure of latest backup ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- unzip -l /root/minecraft/simplebackups/world_2026-05-30_17-10-35.zip | head -n 25")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_zip_structure()
