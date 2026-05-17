import paramiko

def fix_image():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    repo_path = '/home/sparkle/Absolute-Axis'
    
    try:
        client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        
        # Modify docker-compose.yml directly on VM
        print("Modifying docker-compose.yml...")
        sftp = client.open_sftp()
        with sftp.file(f'{repo_path}/docker-compose.yml', 'r') as f:
            content = f.read().decode()
            
        content = content.replace("openjdk:17-slim", "eclipse-temurin:17-jre-jammy")
        
        with sftp.file(f'{repo_path}/docker-compose.yml', 'w') as f:
            f.write(content.encode())
        sftp.close()
        
        # Start containers
        print("Starting containers...")
        cmd = f'cd {repo_path} && echo "{vm_pass}" | sudo -S docker compose up -d minecraft-server'
        stdin, stdout, stderr = client.exec_command(cmd)
        
        print("STDOUT:", stdout.read().decode())
        print("STDERR:", stderr.read().decode())
        
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_image()
