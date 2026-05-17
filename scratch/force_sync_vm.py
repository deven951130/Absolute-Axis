import paramiko
import os
from scp import SCPClient

def sync_all_files():
    vm_ip = '192.168.0.159'
    local_dir = r'e:\absolute axis'
    remote_dir = '/home/sparkle/absolute-axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=20)
        print("Syncing files via SCP...")
        
        with SCPClient(client.get_transport()) as scp:
            # 只同步關鍵資料夾以節省時間
            for folder in ['app', 'static', 'scratch']:
                print(f"Uploading {folder}...")
                scp.put(os.path.join(local_dir, folder), recursive=True, remote_path=remote_dir)
            
            # 單獨上傳 docker-compose.yml
            scp.put(os.path.join(local_dir, 'docker-compose.yml'), remote_path=remote_dir)

        print("Restarting API container...")
        client.exec_command('echo "951130" | sudo -S docker restart axis-server')
        print("Sync Complete!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    sync_all_files()
