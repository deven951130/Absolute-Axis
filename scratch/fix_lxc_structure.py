import paramiko

def fix_lxc_unzip_structure():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Locating run.sh in LXC...")
        stdin, stdout, stderr = client.exec_command('find /root/minecraft -name "run.sh"')
        path = stdout.read().decode().strip()
        print(f"Found run.sh at: {path}")
        
        if path:
            folder = path.replace('/run.sh', '')
            print(f"Moving all files from {folder} to /root/minecraft...")
            client.exec_command(f'mv {folder}/* /root/minecraft/')
            client.exec_command('chmod +x /root/minecraft/run.sh')
            
            print("Starting again...")
            client.exec_command('cd /root/minecraft && screen -dmS mc bash run.sh')
            
            print("Checking Java processes after 5s...")
            import time
            time.sleep(5)
            stdin, stdout, stderr = client.exec_command('ps aux | grep java')
            print(stdout.read().decode())
        else:
            print("CRITICAL: run.sh not found. Something is wrong with the zip content.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_lxc_unzip_structure()
