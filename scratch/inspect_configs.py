import paramiko

def inspect_configs():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== user_jvm_args.txt ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- cat /root/minecraft/user_jvm_args.txt")
        print(stdout.read().decode())
        
        print("=== server.properties ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- cat /root/minecraft/server.properties")
        print(stdout.read().decode())
        
        print("=== Check free memory and cpu info inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- free -m; pct exec 102 -- lscpu | grep -E 'CPU\(s\)|Model name'")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    inspect_configs()
