import paramiko

def optimize_minecraft():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        # 1. 備份原有設定檔
        print("[*] 正在備份原有設定檔...")
        client.exec_command("pct exec 102 -- cp /root/minecraft/user_jvm_args.txt /root/minecraft/user_jvm_args.txt.bak")
        client.exec_command("pct exec 102 -- cp /root/minecraft/server.properties /root/minecraft/server.properties.bak")
        
        # 2. 寫入優化後的 JVM 參數
        print("[*] 正在更新 user_jvm_args.txt...")
        jvm_args = """-Xmx14G
-Xms14G
-Dforge.readTimeout=300
-XX:+UseG1GC
-XX:+ParallelRefProcEnabled
-XX:MaxGCPauseMillis=200
-XX:+UnlockExperimentalVMOptions
-XX:+DisableExplicitGC
-XX:+AlwaysPreTouch
-XX:G1NewSizePercent=30
-XX:G1MaxNewSizePercent=40
-XX:G1HeapRegionSize=8m
-XX:G1ReservePercent=20
-XX:G1HeapWastePercent=5
-XX:G1MixedGCCountTarget=4
-XX:InitiatingHeapFraction=15
-XX:G1MixedGCLiveThresholdPercent=90
-XX:G1RSetUpdatingPauseTimePercent=5
-XX:SurvivorRatio=32
-XX:+PerfDisableSharedMem
-XX:MaxTenuringThreshold=1
"""
        # 使用 pct exec 寫入
        # 注意要轉義換行
        safe_jvm_args = jvm_args.replace("'", "'\\''")
        stdin, stdout, stderr = client.exec_command(f"pct exec 102 -- bash -c \"cat << 'EOF' > /root/minecraft/user_jvm_args.txt\n{safe_jvm_args}\nEOF\"")
        print(stdout.read().decode())
        print(stderr.read().decode())

        # 3. 優化 server.properties（關閉同步磁碟寫入以提升效能，避免區塊載入卡頓）
        print("[*] 正在優化 server.properties...")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- sed -i 's/sync-chunk-writes=true/sync-chunk-writes=false/g' /root/minecraft/server.properties")
        print(stdout.read().decode())
        print(stderr.read().decode())

        # 4. 重啟 Minecraft 服務
        print("[*] 正在重啟 Minecraft 服務 (systemctl restart minecraft.service)...")
        client.exec_command("pct exec 102 -- systemctl restart minecraft.service")
        
        print("[+] 優化完成！正在啟動伺服器...")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    optimize_minecraft()
