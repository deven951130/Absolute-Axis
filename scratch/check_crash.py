import paramiko

def check_crash_logs():
    VM_IP = '192.168.0.159'
    VM_USER = 'sparkle'
    VM_PASS = '951130'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
        
        # 1. 容器狀態
        print("[1] Docker 容器狀態:")
        stdin, stdout, stderr = client.exec_command('docker ps -a --filter "name=axis-server" --format "{{.Names}} | {{.Status}}"')
        print(f"    {stdout.read().decode().strip()}\n")
        
        # 2. 容器日誌（最後 50 行）
        print("[2] axis-server 容器日誌 (最後 50 行):")
        stdin, stdout, stderr = client.exec_command('docker logs axis-server --tail 50 2>&1')
        print(stdout.read().decode().strip())
        
    except Exception as e:
        print(f"[-] 錯誤: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_crash_logs()
