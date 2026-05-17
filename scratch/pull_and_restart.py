import paramiko
import time

def pull_and_restart():
    VM_IP = '192.168.0.159'
    VM_USER = 'sparkle'
    VM_PASS = '951130'
    REPO_PATH = '/home/sparkle/Absolute-Axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"[*] 連線至 VM ({VM_IP})...")
        client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
        print("[+] 連線成功\n")
        
        # Step 1: git pull
        print("[1] 同步最新程式碼...")
        stdin, stdout, stderr = client.exec_command(
            f'cd {REPO_PATH} && git fetch origin && git reset --hard origin/main 2>&1'
        )
        out = stdout.read().decode().strip()
        print(f"    {out}\n")
        
        time.sleep(2)
        
        # Step 2: 驗證關鍵新檔案是否存在
        print("[2] 驗證新檔案...")
        for f in ['static/index.html', 'static/js/multiverse.js', 
                  'static/components/views/multiverse.html', 'app/routers/minecraft.py']:
            stdin, stdout, stderr = client.exec_command(f'grep -c "multiverse" {REPO_PATH}/{f} 2>/dev/null || echo "0"')
            raw = stdout.read().decode().strip()
            # 取第一行的數字，避免多行輸出導致 int() 解析失敗
            count_str = raw.split('\n')[0].strip()
            try:
                count = int(count_str)
            except ValueError:
                count = 0
            status = "✓" if count > 0 else "✗ 未找到（代表 git pull 尚未含此檔案）"
            print(f"    {f}: {status}")

        
        print()
        
        # Step 3: 重啟容器
        print("[3] 重啟 axis-server...")
        stdin, stdout, stderr = client.exec_command(
            f'echo "{VM_PASS}" | sudo -S docker restart axis-server 2>&1'
        )
        out = stdout.read().decode().strip()
        print(f"    {out}")
        print("    等待容器啟動...")
        time.sleep(8)
        
        # Step 4: 確認
        stdin, stdout, stderr = client.exec_command(
            'docker ps --filter "name=axis-server" --format "{{.Status}}"'
        )
        st = stdout.read().decode().strip()
        print(f"\n[+] 容器狀態: {st}")
        print("[+] 完成！請在瀏覽器按 Ctrl+Shift+R 強制刷新。")
        
    except Exception as e:
        print(f"[-] 錯誤: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    pull_and_restart()
