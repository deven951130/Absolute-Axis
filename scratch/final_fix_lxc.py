import paramiko

def final_fix_lxc():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        # 1. 檢查目錄內容
        print("Checking directory contents...")
        stdin, stdout, stderr = client.exec_command('ls -F /root/minecraft/')
        print(stdout.read().decode())
        
        # 2. 檢查 run.sh 權限
        print("Fixing permissions for run.sh...")
        client.exec_command('chmod +x /root/minecraft/run.sh')
        
        # 3. 強制啟動並捕捉即時日誌
        print("Attempting to run run.sh directly to see errors...")
        # 這裡不使用 screen 測試一下
        stdin, stdout, stderr = client.exec_command('cd /root/minecraft/ && ./run.sh', timeout=15)
        # 讀取一部分輸出看發生什麼事
        try:
            print("STDOUT:", stdout.read().decode())
            print("STDERR:", stderr.read().decode())
        except:
            print("Command likely started or timed out as expected.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    final_fix_lxc()
