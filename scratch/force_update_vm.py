import paramiko
import time

def force_update_vm():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ip = '192.168.0.159'
    user = 'sparkle'
    password = '951130'
    
    try:
        print(f"Connecting to VM {ip} as {user}...")
        client.connect(ip, username=user, password=password, timeout=10)
        print("Connected!")
        
        # Determine path
        stdin, stdout, stderr = client.exec_command('find ~ -maxdepth 2 -name "Absolute-Axis" -type d')
        repo_path = stdout.read().decode().strip()
        if not repo_path: repo_path = "~/Absolute-Axis"
        
        print(f"Forcing code sync in {repo_path}...")
        
        # 1. Fetch
        client.exec_command(f'cd {repo_path} && git fetch --all')
        time.sleep(2)
        
        # 2. Hard Reset (This will discard local changes in the VM)
        print("Executing git reset --hard...")
        stdin, stdout, stderr = client.exec_command(f'cd {repo_path} && git reset --hard origin/main')
        print("Reset STDOUT:", stdout.read().decode())
        print("Reset STDERR:", stderr.read().decode())
        
        # 3. Clean untracked files that conflict
        print("Cleaning untracked files...")
        client.exec_command(f'cd {repo_path} && git clean -fd')
        
        # 4. Restart Docker
        print("Restarting axis-server...")
        cmd = f'echo "{password}" | sudo -S docker restart axis-server'
        stdin, stdout, stderr = client.exec_command(cmd)
        print("Restart STDOUT:", stdout.read().decode())
        
        # 5. Final Check - print the sensors part of the system.py file to verify it's the new one
        print("Verifying code in VM...")
        stdin, stdout, stderr = client.exec_command(f'grep -A 20 "room_temp =" {repo_path}/app/routers/system.py')
        print("Grep output:\n", stdout.read().decode())
        
        print("Force update completed.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    force_update_vm()
