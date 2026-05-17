import paramiko

def fix_docker():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    repo_path = '/home/sparkle/Absolute-Axis'
    
    try:
        client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        print("Starting containers with 'docker compose'...")
        cmd = f'cd {repo_path} && echo "{vm_pass}" | sudo -S docker compose up -d minecraft-server && echo "{vm_pass}" | sudo -S docker restart axis-server'
        stdin, stdout, stderr = client.exec_command(cmd)
        
        print("DOCKER STDOUT:", stdout.read().decode())
        print("DOCKER STDERR:", stderr.read().decode())
        print("Fix applied successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_docker()
