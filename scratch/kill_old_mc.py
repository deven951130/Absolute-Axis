import paramiko

def kill_old_mc():
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        
        print("STOPPING AND REMOVING STUCK AXIS-MC CONTAINER ON VM 100...")
        # 強制停止並移除容器
        cmd = 'echo "951130" | sudo -S docker rm -f axis-mc'
        stdin, stdout, stderr = client.exec_command(cmd)
        print("Remove status:", stdout.read().decode())
        
        # 檢查是否還有 Java 進程殘留
        print("Killing any remaining Java processes on VM 100...")
        cmd_kill = 'echo "951130" | sudo -S pkill -9 java'
        client.exec_command(cmd_kill)
        
        print("Checking memory after cleanup...")
        stdin, stdout, stderr = client.exec_command('free -m')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    kill_old_mc()
