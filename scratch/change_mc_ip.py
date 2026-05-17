import paramiko
import time
import socket

def change_lxc_ip():
    px_ip = '192.168.0.138'
    px_user = 'root'
    px_pass = 'deven951130'
    lxc_id = '102'
    new_ip = '192.168.0.130'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"[*] 正在連線至 Proxmox VE 宿主機 ({px_ip})...")
        client.connect(px_ip, username=px_user, password=px_pass, timeout=10)
        print("[+] 連線成功！")
        
        # 1. 取得目前網路設定以防萬一
        print(f"[*] 讀取 LXC {lxc_id} 目前的網路設定...")
        stdin, stdout, stderr = client.exec_command(f'pct config {lxc_id} | grep net0')
        current_net = stdout.read().decode().strip()
        print(f"    目前 net0 設定: {current_net}")
        
        # 2. 變更 IP 位址至 192.168.0.130
        print(f"[*] 正在將 LXC {lxc_id} 的 IP 變更為 {new_ip}/24...")
        # 我們保持原本的橋接 vmbr0 與名稱 eth0，僅更改 IP 與閘道器
        cmd_set_ip = f'pct set {lxc_id} -net0 name=eth0,bridge=vmbr0,ip={new_ip}/24,gw=192.168.0.1'
        stdin, stdout, stderr = client.exec_command(cmd_set_ip)
        err = stderr.read().decode().strip()
        if err:
            print(f"[-] 警告/錯誤: {err}")
        else:
            print("[+] IP 配置更新成功！")
            
        # 3. 重啟容器以套用變更
        print(f"[*] 正在重啟 LXC {lxc_id} 容器以套用網路設定...")
        client.exec_command(f'pct reboot {lxc_id}')
        print("[+] 已送出重啟指令，等待容器引導...")
        
    except Exception as e:
        print(f"[-] 發生錯誤: {e}")
        if client:
            client.close()
        return
    finally:
        if client:
            client.close()
            
    # 4. 輪詢檢測新 IP 連線狀態
    print(f"[*] 開始輪詢檢測新 IP 連線狀態 ({new_ip}:25565)...")
    retry_count = 30
    for i in range(retry_count):
        time.sleep(2)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                if s.connect_ex((new_ip, 25565)) == 0:
                    print(f"\n[+] 成功！Minecraft 伺服器已在新 IP {new_ip}:25565 上線！")
                    return
        except:
            pass
        print(".", end="", flush=True)
        
    print(f"\n[-] 輪詢超時，請檢查 LXC {lxc_id} 內部 Minecraft 服務是否已啟動。")

if __name__ == "__main__":
    change_lxc_ip()
