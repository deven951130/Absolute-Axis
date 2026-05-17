import paramiko
import os
from scp import SCPClient

def fix_perms_and_sync():
    vm_ip = '192.168.0.159'
    local_dir = r'e:\absolute axis'
    remote_dir = '/home/sparkle/Absolute-Axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=20)
        
        print("Taking ownership of the directory...")
        client.exec_command('echo "951130" | sudo -S chown -R sparkle:sparkle /home/sparkle/Absolute-Axis')
        
        print(f"Syncing to: {remote_dir}")
        with SCPClient(client.get_transport()) as scp:
            for folder in ['app', 'static']:
                # 排除 pycache
                local_folder = os.path.join(local_dir, folder)
                print(f"Uploading {folder}...")
                scp.put(local_folder, recursive=True, remote_path=remote_dir)
            
            scp.put(os.path.join(local_dir, 'docker-compose.yml'), remote_path=remote_dir)

        print("Force Rebuilding Container...")
        client.exec_command('echo "951130" | sudo -S docker stop axis-server')
        client.exec_command('echo "951130" | sudo -S docker rm axis-server')
        stdin, stdout, stderr = client.exec_command(f'cd {remote_dir} && echo "951130" | sudo -S docker-compose up -d axis-server')
        print(stdout.read().decode())
        
        print("Finalizing...")
        import time
        time.sleep(3)
        print("DONE! Please refresh now.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_perms_and_sync()
