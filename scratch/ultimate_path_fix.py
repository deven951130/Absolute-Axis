import paramiko
import os
from scp import SCPClient

def fix_all_and_rebuild():
    vm_ip = '192.168.0.159'
    local_dir = r'e:\absolute axis'
    # 注意：路徑區分大小寫！
    remote_dir = '/home/sparkle/Absolute-Axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=20)
        print(f"Force syncing to EXACT path: {remote_dir}")
        
        with SCPClient(client.get_transport()) as scp:
            for folder in ['app', 'static']:
                print(f"Uploading {folder}...")
                scp.put(os.path.join(local_dir, folder), recursive=True, remote_path=remote_dir)
            
            print("Uploading critical config files...")
            scp.put(os.path.join(local_dir, 'docker-compose.yml'), remote_path=remote_dir)

        print("Stopping current container...")
        client.exec_command('echo "951130" | sudo -S docker stop axis-server')
        client.exec_command('echo "951130" | sudo -S docker rm axis-server')
        
        print("Re-launching with UP command to ensure mount refresh...")
        # 使用 -d 模式啟動
        stdin, stdout, stderr = client.exec_command(f'cd {remote_dir} && echo "951130" | sudo -S docker-compose up -d axis-server')
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("Wait 5 seconds and check logs...")
        import time
        time.sleep(5)
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker logs --tail 20 axis-server')
        print(stdout.read().decode())
        
        print("FIX COMPLETE!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_all_and_rebuild()
