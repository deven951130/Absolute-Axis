import paramiko

def check_net():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== Checking LXC 102 internet connection ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ping -c 3 8.8.8.8")
        print("Ping 8.8.8.8 stdout:")
        print(stdout.read().decode())
        print("Ping 8.8.8.8 stderr:")
        print(stderr.read().decode())
        
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ping -c 3 google.com")
        print("Ping google.com stdout:")
        print(stdout.read().decode())
        print("Ping google.com stderr:")
        print(stderr.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_net()
