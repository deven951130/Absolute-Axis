import paramiko

def monitor_mc_lxc():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        # 1. 檢查 CPU 與 記憶體 即時使用率
        print("Checking container hardware load...")
        stdin, stdout, stderr = client.exec_command('top -b -n 1 | head -n 15')
        print(stdout.read().decode())
        
        # 2. 檢查 Java 是否在跑
        print("Checking Java processes...")
        stdin, stdout, stderr = client.exec_command('ps aux | grep java')
        print(stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    monitor_mc_lxc()
