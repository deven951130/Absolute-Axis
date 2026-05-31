import paramiko
import time

def restore_previous_backup():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    backup_file = "world_2026-05-31_03-10-37.zip" # 台灣時間 05-31 11:10:37 的備份
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        # 1. 停止 Minecraft 服務
        print("[*] 正在停止 Minecraft 伺服器服務...")
        client.exec_command("pct exec 102 -- systemctl stop minecraft.service")
        
        # 等待 Java 程序完全結束
        print("[*] 正在確認 Java 程序是否已結束...")
        java_running = True
        for i in range(15):
            stdin, stdout, stderr = client.exec_command("pct exec 102 -- ps aux | grep java")
            ps_out = stdout.read().decode()
            java_processes = [line for line in ps_out.splitlines() if "java" in line and "grep" not in line]
            if not java_processes:
                java_running = False
                break
            print(f"[*] Java 程序仍運行中，等待中 ({i+1}/15)...")
            time.sleep(2)
            
        if java_running:
            print("[-] 警告：Java 程序在 30 秒內未完全結束。")
        else:
            print("[+] Minecraft 伺服器已成功停止。")
            
        # 2. 備份現有的 world 目錄以防萬一
        timestamp = int(time.time())
        backup_dir = f"world_backup_before_rollback_{timestamp}"
        print(f"[*] 正在將現有的 world 資料夾備份為 {backup_dir}...")
        client.exec_command(f"pct exec 102 -- mv /root/minecraft/world /root/minecraft/{backup_dir}")
        
        # 3. 還原指定的上一個備份檔
        backup_path = f"/root/minecraft/simplebackups/{backup_file}"
        print(f"[*] 正在解壓縮指定的備份檔案 {backup_file}...")
        stdin, stdout, stderr = client.exec_command(f"pct exec 102 -- unzip -q -o {backup_path} -d /root/minecraft")
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status == 0:
            print("[+] 備份解壓縮完成。")
        else:
            print(f"[-] 解壓縮失敗，結束代碼：{exit_status}")
            print(stderr.read().decode())
            # 還原舊的
            client.exec_command(f"pct exec 102 -- mv /root/minecraft/{backup_dir} /root/minecraft/world")
            return
            
        # 4. 啟動 Minecraft 服務
        print("[*] 正在重新啟動 Minecraft 服務...")
        client.exec_command("pct exec 102 -- systemctl reset-failed minecraft.service")
        client.exec_command("pct exec 102 -- systemctl start minecraft.service")
        
        print("[*] 等待 5 秒...")
        time.sleep(5)
        
        print("=== Minecraft 服務最新狀態 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- systemctl status minecraft.service")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    restore_previous_backup()
