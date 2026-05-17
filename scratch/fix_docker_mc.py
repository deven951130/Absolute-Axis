import paramiko

def fix_server_and_compose():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    repo_path = '/home/sparkle/Absolute-Axis'
    
    try:
        client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        
        # Add Memory Limits to JVM Args
        print("Adding -Xmx10G -Xms10G to user_jvm_args.txt...")
        client.exec_command(f'echo "-Xmx10G" >> {repo_path}/minecraft-data/user_jvm_args.txt')
        client.exec_command(f'echo "-Xms10G" >> {repo_path}/minecraft-data/user_jvm_args.txt')
        
        # Modify docker-compose.yml directly on VM
        print("Modifying docker-compose.yml...")
        new_compose = """
  minecraft-server:
    image: openjdk:17-slim
    container_name: axis-mc
    restart: unless-stopped
    ports:
      - "25565:25565"
    working_dir: /data
    command: bash run.sh
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 10.5G
    volumes:
      - ./minecraft-data:/data
"""
        # Read the file
        sftp = client.open_sftp()
        with sftp.file(f'{repo_path}/docker-compose.yml', 'r') as f:
            content = f.read().decode()
            
        # Replace the minecraft-server block
        import re
        content = re.sub(r'  minecraft-server:.*?(?=\n\S|\Z)', new_compose, content, flags=re.DOTALL)
        
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
    fix_server_and_compose()
