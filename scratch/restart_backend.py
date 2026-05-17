import paramiko

def restart_backend():
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    repo_path = '/home/sparkle/Absolute-Axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        print("Pulling git and restarting axis-server...")
        client.exec_command(f'cd {repo_path} && git pull origin main')
        client.exec_command('echo "951130" | sudo -S docker restart axis-server')
        print("Restart complete.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    restart_backend()
