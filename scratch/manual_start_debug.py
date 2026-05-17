import paramiko

def manual_start_no_screen():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Checking java version...")
        client.exec_command('java -version')
        
        print("Executing start command with full path...")
        # 嘗試直接啟動，並將輸出導向到文件以便查看
        cmd = 'cd /root/minecraft && ./run.sh > /root/boot.log 2>&1 &'
        client.exec_command(cmd)
        
        print("Waiting 5s and checking boot.log...")
        import time
        time.sleep(5)
        stdin, stdout, stderr = client.exec_command('cat /root/boot.log')
        print(stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    manual_start_no_screen()
