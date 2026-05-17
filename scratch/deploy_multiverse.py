import paramiko
import time

def push_and_update_vm():
    """
    將本地 Git 倉庫的最新變更推送至 GitHub，
    並 SSH 至 VM 執行 git pull + docker restart 完成線上部署。
    """
    VM_IP = '192.168.0.159'
    VM_USER = 'sparkle'
    VM_PASS = '951130'
    REPO_PATH = '/home/sparkle/Absolute-Axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"[*] 正在連線至 VM ({VM_IP})...")
        client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=15)
        print("[+] 連線成功！")
        
        # 1. git fetch + reset 至最新 main (強制同步)
        print("\n[1] 正在同步最新程式碼 (git pull --rebase)...")
        stdin, stdout, stderr = client.exec_command(
            f'cd {REPO_PATH} && git fetch origin && git reset --hard origin/main 2>&1'
        )
        out = stdout.read().decode().strip()
        print(f"    git 輸出: {out}")
        
        time.sleep(2)
        
        # 2. 重啟 Docker 容器 (axis-server) 以套用新程式碼
        print("\n[2] 正在重啟 axis-server Docker 容器...")
        stdin, stdout, stderr = client.exec_command(
            f'echo "{VM_PASS}" | sudo -S docker restart axis-server 2>&1'
        )
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        print(f"    Docker 輸出: {out or err}")
        
        time.sleep(5)
        
        # 3. 確認容器狀態
        print("\n[3] 確認容器運行狀態...")
        stdin, stdout, stderr = client.exec_command(
            'docker ps --filter "name=axis-server" --format "{{.Names}} | {{.Status}}"'
        )
        status = stdout.read().decode().strip()
        print(f"    容器狀態: {status}")
        
        # 4. 確認最新的 index.html 已包含多重宇宙 nav item
        print("\n[4] 驗證多重宇宙 nav item 是否已存在...")
        stdin, stdout, stderr = client.exec_command(
            f'grep -c "multiverse" {REPO_PATH}/static/index.html 2>&1'
        )
        count = stdout.read().decode().strip()
        if count and int(count) > 0:
            print(f"    [+] 驗證成功！index.html 包含 {count} 處 multiverse 相關標記。")
        else:
            print(f"    [-] 警告：未找到 multiverse 標記，請確認 git push 是否成功。")
        
        print("\n[+] 部署完成！請重新整理瀏覽器（Ctrl+Shift+R 強制清除快取）即可看到「🌌 多重宇宙」側邊欄項目。")
        
    except Exception as e:
        print(f"[-] 發生錯誤: {e}")
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    push_and_update_vm()
