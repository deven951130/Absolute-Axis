import paramiko

def debug_mc_boot():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        # 1. 直接查看日誌輸出
        print("Reading latest logs from /root/minecraft/logs/latest.log...")
        stdin, stdout, stderr = client.exec_command('tail -n 20 /root/minecraft/logs/latest.log')
        print(stdout.read().decode())
        
        # 2. 如果沒啟動，嘗試手動直接啟動（不進入 screen 以便看報錯）
        print("Checking screen logs...")
        stdin, stdout, stderr = client.exec_command('ls -l /root/minecraft/')
        print(stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    debug_mc_boot()
