import paramiko

def diagnose_timeout():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== LXC 102 Status ===")
        stdin, stdout, stderr = client.exec_command("pct list")
        print(stdout.read().decode())
        
        print("=== LXC 102 Resource Usage inside container ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- free -h; pct exec 102 -- uptime; pct exec 102 -- df -h")
        print(stdout.read().decode())
        
        print("=== Check Java processes inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ps aux | grep java")
        print(stdout.read().decode())
        
        print("=== List of recent crash reports ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ls -la /root/minecraft/crash-reports")
        print(stdout.read().decode())
        
        print("=== Last 100 lines of Minecraft latest.log ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- tail -n 100 /root/minecraft/logs/latest.log")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    diagnose_timeout();
