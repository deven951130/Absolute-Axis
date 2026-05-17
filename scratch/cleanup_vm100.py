import paramiko

def cleanup_vm100():
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    repo_path = '/home/sparkle/Absolute-Axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        print("Stopping axis-mc container...")
        client.exec_command('echo "951130" | sudo -S docker stop axis-mc && echo "951130" | sudo -S docker rm axis-mc')
        
        print("Removing axis-mc from docker-compose.yml...")
        # Just run a sed command to remove the minecraft-server section.
        # It's at the end of the file.
        cmd_sed = f"sed -i '/minecraft-server:/,$d' {repo_path}/docker-compose.yml"
        client.exec_command(cmd_sed)
        
        print("Cleanup complete.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    cleanup_vm100()
