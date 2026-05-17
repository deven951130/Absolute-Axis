import paramiko
import socket

def check_realtime_status():
    px_ip = '192.168.0.138'
    px_user = 'root'
    px_pass = 'deven951130'
    lxc_id = '102'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"[*] 正在連線至 Proxmox VE 宿主機 ({px_ip})...")
        client.connect(px_ip, username=px_user, password=px_pass, timeout=10)
        print("[+] 連線成功！")
        
        # 1. 取得目前網路配置
        stdin, stdout, stderr = client.exec_command(f'pct config {lxc_id} | grep net0')
        net_cfg = stdout.read().decode().strip()
        print(f"[1] LXC {lxc_id} 網路配置:")
        print(f"    {net_cfg}")
        
        # 解析配置中的 IP
        current_ip = "未知"
        if "ip=" in net_cfg:
            current_ip = net_cfg.split("ip=")[1].split(",")[0].split("/")[0]
            print(f"    目前配置的 IP 為: {current_ip}")
            
        # 2. 取得容器運作狀態
        stdin, stdout, stderr = client.exec_command(f'pct status {lxc_id}')
        status = stdout.read().decode().strip()
        print(f"[2] LXC {lxc_id} 容器狀態: {status}")
        
        if "status: stopped" in status:
            print("[-] 警告: 容器目前處於關閉狀態！請執行 `pct start 102` 啟動容器。")
            return
            
        # 3. 測試容器內的 Java 進程監聽狀態
        print(f"[3] 檢查容器內 Java 連接埠監聽...")
        stdin, stdout, stderr = client.exec_command(f"pct exec {lxc_id} -- ss -tulpn | grep 25565")
        ss_out = stdout.read().decode().strip()
        if ss_out:
            print(f"    監聽成功:\n    {ss_out}")
            
            # 4. 內網直接 TCP 測試
            print(f"[4] 自本地端向該 IP ({current_ip}:25565) 發送 TCP 連線測試...")
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2.0)
                    if s.connect_ex((current_ip, 25565)) == 0:
                        print(f"    [+] 內網連線測試成功！{current_ip}:25565 運作完全正常。")
                    else:
                        print(f"    [-] 內網連線失敗！TCP 連線被拒絕。")
            except Exception as se:
                print(f"    [-] 測試時發生 socket 異常: {se}")
        else:
            print("    [-] 警告: 容器內沒有任何程式在監聽 25565 埠！")
            print("    [原因] LXC 容器已開機，但內部的 Minecraft 伺服器並未被啟動。")
            print("    [解法] 請手動 SSH 登入容器執行啟動，或執行 `configure_mc_autostart.py` 設定開機自啟。")

    except Exception as e:
        print(f"[-] 發生錯誤: {e}")
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    check_realtime_status()
