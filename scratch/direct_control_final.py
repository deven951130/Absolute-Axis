import paramiko
import time

def direct_control_with_password():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ip = '192.168.0.159'
    user = 'sparkle'
    password = '951130'
    
    try:
        print(f"Connecting to VM {ip} as {user}...")
        client.connect(ip, username=user, password=password, timeout=10)
        print("Connected!")
        
        # 1. Find the Absolute-Axis directory
        print("Finding project directory...")
        stdin, stdout, stderr = client.exec_command('find ~ -maxdepth 2 -name "Absolute-Axis" -type d')
        repo_path = stdout.read().decode().strip()
        
        if not repo_path:
            repo_path = "~/Absolute-Axis"
            
        print(f"Repo path: {repo_path}")
        
        # 2. Pull code
        print("Pulling latest code...")
        stdin, stdout, stderr = client.exec_command(f'cd {repo_path} && git pull origin main')
        print("Pull STDOUT:", stdout.read().decode())
        print("Pull STDERR:", stderr.read().decode())
        
        # 3. Restart Docker Container
        # Using -S to read password from stdin for sudo
        print("Restarting axis-server container...")
        cmd = f'cd {repo_path} && echo "{password}" | sudo -S docker restart axis-server'
        stdin, stdout, stderr = client.exec_command(cmd)
        print("Restart STDOUT:", stdout.read().decode())
        print("Restart STDERR:", stderr.read().decode())
        
        # 4. Also install QEMU Guest Agent to make future control easier
        print("Ensuring QEMU Guest Agent is installed for future control...")
        cmd_agent = f'echo "{password}" | sudo -S apt-get update && echo "{password}" | sudo -S apt-get install -y qemu-guest-agent && echo "{password}" | sudo -S systemctl enable --now qemu-guest-agent'
        # We don't want to wait forever for apt update, but let's try
        client.exec_command(cmd_agent)
        print("Guest agent install command sent.")
        
        print("All tasks completed successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    direct_control_with_password()
