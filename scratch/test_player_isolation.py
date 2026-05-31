import paramiko

def isolate_player():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    uuid = "34dfd324-7f04-3973-9ec2-8fe28e448276"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        # 1. 停止 Minecraft 服務
        print("[*] 正在停止 Minecraft 服務...")
        client.exec_command("pct exec 102 -- systemctl stop minecraft.service")
        
        # 等待停止
        import time
        time.sleep(5)
        
        # 2. 備份並暫時移出玩家資料檔
        print(f"[*] 正在處理玩家 {uuid} 的資料檔...")
        # 檢查檔案是否存在
        stdin, stdout, stderr = client.exec_command(f"pct exec 102 -- ls -la /root/minecraft/world/playerdata/{uuid}.dat")
        file_check = stdout.read().decode()
        if uuid in file_check:
            print("    [+] 找到玩家 .dat 存檔，進行備份並重新命名...")
            client.exec_command(f"pct exec 102 -- mv /root/minecraft/world/playerdata/{uuid}.dat /root/minecraft/world/playerdata/{uuid}.dat.bak")
        else:
            print("    [-] 未找到玩家 .dat 存檔。")
            
        stdin, stdout, stderr = client.exec_command(f"pct exec 102 -- ls -la /root/minecraft/world/playerdata/{uuid}.dat_old")
        file_check_old = stdout.read().decode()
        if uuid in file_check_old:
            print("    [+] 找到玩家 .dat_old 存檔，進行備份並重新命名...")
            client.exec_command(f"pct exec 102 -- mv /root/minecraft/world/playerdata/{uuid}.dat_old /root/minecraft/world/playerdata/{uuid}.dat_old.bak")
            
        # 3. 重新啟動 Minecraft 服務
        print("[*] 正在重新啟動 Minecraft 服務...")
        client.exec_command("pct exec 102 -- systemctl reset-failed minecraft.service")
        client.exec_command("pct exec 102 -- systemctl start minecraft.service")
        
        print("[+] 移出完成。請玩家嘗試重新連線登入。")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    isolate_player()
