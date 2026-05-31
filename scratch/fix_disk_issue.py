import paramiko
import re

def fix_disk():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        # 1. 刪除老舊備份以釋放空間
        print("[*] 正在獲取備份列表...")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ls -la /root/minecraft/simplebackups")
        files_out = stdout.read().decode()
        
        backup_files = []
        for line in files_out.splitlines():
            match = re.search(r'(world_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.zip)', line)
            if match:
                backup_files.append(match.group(1))
                
        backup_files.sort()
        
        # 保留最後 2 個備份，其餘刪除
        if len(backup_files) > 2:
            to_delete = backup_files[:-2]
            print(f"[*] 發現 {len(backup_files)} 個備份，將刪除較舊的 {len(to_delete)} 個，保留最新的 2 個...")
            for old_file in to_delete:
                print(f"    [-] 刪除備份：{old_file}")
                client.exec_command(f"pct exec 102 -- rm /root/minecraft/simplebackups/{old_file}")
        else:
            print("[*] 備份檔案小於或等於 2 個，不進行刪除。")
            
        # 2. 擴展 LXC 102 的硬碟大小 (+10G)
        print("[*] 正在透過 PVE 擴容 LXC 102 根硬碟空間 +10G...")
        stdin, stdout, stderr = client.exec_command("pct resize 102 rootfs +10G")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        # 3. 檢查擴容與清理後的磁碟空間
        print("=== 清理與擴容後 LXC 102 的磁碟空間 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- df -h /")
        print(stdout.read().decode())
        
        # 4. 因為先前磁碟已達 99.8% 滿，JVM 或是系統可能寫入出錯，重啟 Minecraft 服務以策安全
        print("[*] 正在重啟 Minecraft 服務以回復健康寫入狀態...")
        client.exec_command("pct exec 102 -- systemctl restart minecraft.service")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_disk()
