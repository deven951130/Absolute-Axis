import paramiko

def extreme_debug_lxc():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Listing ALL files in LXC /root/minecraft/ recursively...")
        stdin, stdout, stderr = client.exec_command('find /root/minecraft/ -maxdepth 4')
        print(stdout.read().decode())
        
        # 如果發現 run.sh，顯示其路徑並嘗試啟動
        print("Searching specifically for run.sh...")
        stdin, stdout, stderr = client.exec_command('find /root/minecraft/ -name "run.sh"')
        path = stdout.read().decode().strip()
        print(f"Final Path Found: {path}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    extreme_debug_lxc()
