import paramiko

def verify_local():
    VM_IP = '100.118.53.34'
    VM_USER = 'sparkle'
    VM_PASS = '951130'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"[*] 連線至 VM ({VM_IP})...")
        client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
        print("[+] 連線成功\n")
        
        # Test 1: 測試背景圖片存取
        print("[1] 測試背景圖片是否可以存取 (/static/tech_bg.png)...")
        stdin, stdout, stderr = client.exec_command('curl -I http://localhost:8000/static/tech_bg.png 2>&1')
        print(stdout.read().decode())
        
        # Test 2: 測試接案 API 是否可以存取 (/api/gigs)
        print("[2] 測試接案 API (/api/gigs)...")
        stdin, stdout, stderr = client.exec_command('curl -s http://localhost:8000/api/gigs 2>&1')
        print(stdout.read().decode())
        
        # Test 3: 測試 index.css 是否已包含新樣式
        print("\n[3] 檢查 index.css 結尾是否包含新背景與動畫樣式...")
        stdin, stdout, stderr = client.exec_command('tail -n 20 /home/sparkle/Absolute-Axis/static/css/index.css 2>&1')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"[-] 錯誤: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    verify_local()
