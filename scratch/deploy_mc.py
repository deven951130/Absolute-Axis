import paramiko
import os
import time

def deploy_minecraft():
    zip_path = r"c:\Users\tony9\Downloads\test area\【⭐服务端⭐】(开服用，若不清楚请下载客户端\香草纪元：食旅纪行 Server2.6.1.zip"
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    repo_path = '/home/sparkle/Absolute-Axis'
    
    if not os.path.exists(zip_path):
        print(f"File not found: {zip_path}")
        return

    print("Connecting to VM...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
    
    try:
        # Create minecraft-data directory
        client.exec_command(f'mkdir -p {repo_path}/minecraft-data')
        
        # Open SFTP to transfer the file
        print(f"Uploading 1.7GB zip file via SFTP. This may take a few minutes...")
        sftp = client.open_sftp()
        remote_zip = f'{repo_path}/minecraft-data/server.zip'
        
        # Simple progress callback
        last_percent = -1
        def print_progress(transferred, total):
            nonlocal last_percent
            percent = int((transferred / total) * 100)
            if percent % 10 == 0 and percent != last_percent:
                print(f"Upload progress: {percent}%")
                last_percent = percent
                
        sftp.put(zip_path, remote_zip, callback=print_progress)
        sftp.close()
        print("Upload complete!")
        
        # Unzip the file
        print("Extracting zip file on VM (this might take a minute)...")
        # Ensure unzip is installed
        client.exec_command(f'echo "{vm_pass}" | sudo -S apt-get install -y unzip')
        time.sleep(2)
        
        stdin, stdout, stderr = client.exec_command(f'cd {repo_path}/minecraft-data && unzip -o server.zip && rm server.zip')
        exit_status = stdout.channel.recv_exit_status()
        print("Extraction complete.")
        
        # Force sync Absolute-Axis repository
        print("Syncing backend and frontend changes...")
        client.exec_command(f'cd {repo_path} && git fetch --all && git reset --hard origin/main')
        
        # Start the minecraft container and restart the backend server
        print("Starting Minecraft Server container and Axis backend...")
        cmd = f'cd {repo_path} && echo "{vm_pass}" | sudo -S docker-compose up -d minecraft-server && echo "{vm_pass}" | sudo -S docker restart axis-server'
        stdin, stdout, stderr = client.exec_command(cmd)
        print("DOCKER STDOUT:", stdout.read().decode())
        print("DOCKER STDERR:", stderr.read().decode())
        
        print("Deployment successful! Minecraft server is starting.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    deploy_minecraft()
