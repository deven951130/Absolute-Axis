import paramiko
import time
import sys

# PVE 連線資訊
PVE_HOST = '100.124.203.61'
PVE_USER = 'root'
PVE_PASS = 'deven951130'
VM_IP = '192.168.0.159'
PVE_LOCAL_IP = '192.168.0.138'
PORT = 8080

def run_ssh_cmd(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8').strip()
    err = stderr.read().decode('utf-8').strip()
    return out, err

def main():
    print("Connecting to PVE...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(PVE_HOST, username=PVE_USER, password=PVE_PASS, timeout=10)
    except Exception as e:
        print(f"Error connecting to PVE: {e}")
        sys.exit(1)

    print("Checking if SSH key exists on PVE...")
    out, _ = run_ssh_cmd(client, "ls -la /root/.ssh/id_rsa")
    if "No such file or directory" in out or not out:
        print("Generating SSH key on PVE...")
        run_ssh_cmd(client, "ssh-keygen -t rsa -N '' -f /root/.ssh/id_rsa")

    # 建立臨時目錄並複製公鑰
    print("Preparing key server on PVE...")
    run_ssh_cmd(client, "mkdir -p /tmp/pve_pub && cp /root/.ssh/id_rsa.pub /tmp/pve_pub/key")

    # 啟動 HTTP 伺服器
    # 先確保 8080 埠口沒有被佔用
    run_ssh_cmd(client, "fuser -k 8080/tcp") 
    time.sleep(1)
    
    print(f"Starting HTTP Server on PVE port {PORT}...")
    # 使用 Python 3 啟動背景伺服器並取得 PID
    out, _ = run_ssh_cmd(client, f"python3 -m http.server {PORT} --directory /tmp/pve_pub > /dev/null 2>&1 & echo $!")
    server_pid = out.strip()
    print(f"HTTP Server started with PID: {server_pid}")

    # 給使用者指令
    curl_cmd = f"mkdir -p ~/.ssh && curl -s http://{PVE_LOCAL_IP}:{PORT}/key >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
    print("\n" + "="*80)
    print("請在您的 Proxmox noVNC 終端機內輸入以下指令（請務必完整輸入，無複製貼上時可手動輸入）：")
    print(curl_cmd)
    print("="*80 + "\n")
    print("等待您輸入指令... 程式每隔 5 秒會自動偵測連線狀態...")

    # 開始輪詢是否能免密碼登入 VM 100
    connected = False
    max_attempts = 120 # 等待 10 分鐘
    attempt = 0
    
    test_ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -i /root/.ssh/id_rsa sparkle@{VM_IP} 'whoami'"
    
    try:
        while attempt < max_attempts:
            out, err = run_ssh_cmd(client, test_ssh_cmd)
            if out == "sparkle":
                print("\n[SUCCESS] 成功與 VM 建立免密碼 SSH 連線！開始執行更新程序...")
                connected = True
                break
            
            attempt += 1
            sys.stdout.write(f"\r等待中... ({attempt}/{max_attempts})")
            sys.stdout.flush()
            time.sleep(5)
            
        if not connected:
            print("\n[TIMEOUT] 超時未偵測到連線，更新程序終止。")
            cleanup(client, server_pid)
            return

        # 執行更新
        print("步驟 1/3: 執行 git fetch 與 reset...")
        out, err = run_ssh_cmd(client, f"ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa sparkle@{VM_IP} 'cd ~/Absolute-Axis && git fetch --all && git reset --hard origin/main'")
        print("Git Output:\n", out)
        if err:
            print("Git Stderr:\n", err)

        print("步驟 2/3: 重啟 Docker 容器並進行 Build...")
        out, err = run_ssh_cmd(client, f"ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa sparkle@{VM_IP} 'cd ~/Absolute-Axis && docker compose down && docker compose build && docker compose up -d'")
        print("Docker Output:\n", out)
        if err:
            print("Docker Stderr:\n", err)

        print("步驟 3/3: 檢查容器狀態與日誌...")
        out, err = run_ssh_cmd(client, f"ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa sparkle@{VM_IP} 'docker ps'")
        print("Docker Container Status:\n", out)
        
        out, err = run_ssh_cmd(client, f"ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa sparkle@{VM_IP} 'docker logs axis-server --tail 20'")
        print("Uvicorn Logs:\n", out)

        print("\n[FINISHED] 更新已順利完成！請重新整理網頁檢查連線。")

    finally:
        cleanup(client, server_pid)
        client.close()

def cleanup(client, pid):
    print("\nCleaning up key server on PVE...")
    if pid:
        run_ssh_cmd(client, f"kill -9 {pid}")
    run_ssh_cmd(client, "rm -rf /tmp/pve_pub")
    print("Cleanup completed.")

if __name__ == "__main__":
    main()
