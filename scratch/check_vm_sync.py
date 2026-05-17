import paramiko

def check_files():
    vm_ip = '192.168.0.159'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=10)
        print("Checking dashboard.html content on VM 100...")
        # 我們檢查是否有 mc-config 關鍵字
        stdin, stdout, stderr = client.exec_command('grep "mc-config" /home/sparkle/absolute-axis/static/components/views/dashboard.html')
        res = stdout.read().decode()
        if res:
            print(f"Found on VM: {res}")
        else:
            print("NOT FOUND on VM 100! File is out of sync.")
            
        print("\nChecking file path on VM...")
        stdin, stdout, stderr = client.exec_command('ls -l /home/sparkle/absolute-axis/static/components/views/dashboard.html')
        print(stdout.read().decode())
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_files()
