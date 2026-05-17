import paramiko

def update_vm():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ips_to_try = ['192.168.0.159', '100.83.64.84']
    user = 'root'
    password = 'deven951130' # Assuming same password as proxmox
    
    for ip in ips_to_try:
        try:
            print(f"Trying to connect to {ip}...")
            client.connect(ip, username=user, password=password, timeout=5)
            print("Connected!")
            
            # Find the repo
            print("Looking for Absolute-Axis repo...")
            stdin, stdout, stderr = client.exec_command('find / -name "Absolute-Axis" -type d 2>/dev/null | grep -v "/var/lib/docker"')
            repos = stdout.read().decode().strip().split('\n')
            
            repo_path = ""
            for r in repos:
                if r:
                    repo_path = r
                    break
            
            if not repo_path:
                print("Could not find repo directory. Checking /root/Absolute-Axis...")
                repo_path = "/root/Absolute-Axis"
            
            print(f"Using repo path: {repo_path}")
            
            cmd = f"cd {repo_path} && git pull origin main && docker restart axis-server"
            print(f"Executing: {cmd}")
            stdin, stdout, stderr = client.exec_command(cmd)
            print("STDOUT:", stdout.read().decode())
            print("STDERR:", stderr.read().decode())
            
            return
        except Exception as e:
            print(f"Failed on {ip}: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    update_vm()
