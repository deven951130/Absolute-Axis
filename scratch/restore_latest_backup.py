import paramiko
import time
import re

def restore_latest_backup():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        # 1. 取得備份檔案列表並找出最新的備份檔
        print("[*] 正在獲取備份檔案列表...")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ls -la /root/minecraft/simplebackups")
        files_out = stdout.read().decode()
        
        backup_files = []
        for line in files_out.splitlines():
            # 匹配例如 world_2026-05-30_17-10-35.zip 的檔案
            match = re.search(r'(world_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.zip)', line)
            if match:
                backup_files.append(match.group(1))
        
        if not backup_files:
            print("[-] 錯誤：找不到任何 Minecraft 世界備份檔。")
            return
            
        # 排序以獲得最新的檔案
        backup_files.sort()
        latest_backup = backup_files[-1]
        print(f"[+] 找到最新的備份檔案：{latest_backup}")
        
        # 2. 停止 Minecraft 伺服器服務
        print("[*] 正在停止 Minecraft 伺服器服務 (systemctl stop minecraft.service)...")
        client.exec_command("pct exec 102 -- systemctl stop minecraft.service")
        
        # 等待服務完全停止並檢查 Java 程序是否已結束
        print("[*] 正在確認 Java 程序是否已完全結束...")
        java_running = True
        for i in range(15):
            stdin, stdout, stderr = client.exec_command("pct exec 102 -- ps aux | grep java")
            ps_out = stdout.read().decode()
            # 過濾掉 grep 自己
            java_processes = [line for line in ps_out.splitlines() if "java" in line and "grep" not in line]
            if not java_processes:
                java_running = False
                break
            print(f"[*] Java 程序仍在執行中，等待中 ({i+1}/15)...")
            time.sleep(2)
            
        if java_running:
            print("[-] 警告：Java 程序在 30 秒內未完全結束。強制進行下一步，但可能會有檔案鎖定風險。")
        else:
            print("[+] Minecraft 伺服器已成功停止。")
            
        # 3. 備份當前的 world 資料夾，以防萬一
        timestamp = int(time.time())
        backup_dir_name = f"world_backup_before_restore_{timestamp}"
        print(f"[*] 正在將現有的 world 資料夾重新命名為 {backup_dir_name}...")
        stdin, stdout, stderr = client.exec_command(f"pct exec 102 -- mv /root/minecraft/world /root/minecraft/{backup_dir_name}")
        err_out = stderr.read().decode().strip()
        if err_out:
            print(f"[*] 重新命名提示：{err_out} (若原本無此資料夾則屬正常)")
            
        # 4. 解壓縮最新的備份檔
        backup_path = f"/root/minecraft/simplebackups/{latest_backup}"
        print(f"[*] 正在解壓縮備份檔案 {latest_backup} 至 /root/minecraft...")
        # -o 代表覆蓋不提示，-q 代表靜音模式避免過多輸出
        stdin, stdout, stderr = client.exec_command(f"pct exec 102 -- unzip -q -o {backup_path} -d /root/minecraft")
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status == 0:
            print("[+] 備份解壓縮完成。")
        else:
            print(f"[-] 解壓縮失敗，結束代碼：{exit_status}")
            print(stderr.read().decode())
            # 嘗試還原剛才搬移的 world
            client.exec_command(f"pct exec 102 -- mv /root/minecraft/{backup_dir_name} /root/minecraft/world")
            return
            
        # 5. 重新啟動 Minecraft 伺服器服務
        print("[*] 正在啟動 Minecraft 伺服器服務...")
        client.exec_command("pct exec 102 -- systemctl start minecraft.service")
        time.sleep(5)
        
        # 6. 驗證服務狀態
        print("=== Minecraft 服務最新狀態 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- systemctl status minecraft.service")
        print(stdout.read().decode())
        
        print("=== Minecraft 最新啟動日誌 (15 行) ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- tail -n 15 /root/minecraft/logs/latest.log")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    restore_latest_backup()
