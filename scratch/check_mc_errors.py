import paramiko

def check_mc_errors():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== Checking errors in latest.log ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- grep -i -E 'error|exception|fail' /root/minecraft/logs/latest.log | tail -n 50")
        print(stdout.read().decode())
        
        print("=== Checking if there are any warnings/errors on join ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- grep -B 5 -A 10 'sparkle_0229' /root/minecraft/logs/latest.log | tail -n 60")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_mc_errors()
