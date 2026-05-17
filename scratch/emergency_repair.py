import paramiko

def repair_tunnel():
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Connecting to VM 100 to repair Cloudflare Tunnel...")
        client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        
        # 1. 檢查 Docker 狀態並重新啟動關鍵容器
        print("Restarting axis-cloudflared and axis-server...")
        cmd = 'echo "951130" | sudo -S docker restart axis-cloudflared axis-server'
        stdin, stdout, stderr = client.exec_command(cmd)
        print("Result:", stdout.read().decode())
        
        # 2. 檢查系統記憶體剩餘量
        print("Checking current memory usage...")
        stdin, stdout, stderr = client.exec_command('free -m')
        print(stdout.read().decode())
        
        print("Repair complete.")
    except Exception as e:
        print(f"Error during repair: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    repair_tunnel()
