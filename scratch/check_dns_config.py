import paramiko

def check_dns_config():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== LXC 102 /etc/resolv.conf ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- cat /etc/resolv.conf")
        print(stdout.read().decode())
        
        print("=== PVE Host /etc/resolv.conf ===")
        stdin, stdout, stderr = client.exec_command("cat /etc/resolv.conf")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_dns_config()
