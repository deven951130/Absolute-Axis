import paramiko

def configure_autostart():
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
        
        # 1. 設定 LXC 容器開機自啟動 (onboot=1)
        print(f"[*] 正在設定 LXC 容器 {lxc_id} 在 PVE 宿主機開機時自動啟動...")
        stdin, stdout, stderr = client.exec_command(f'pct set {lxc_id} --onboot 1')
        err = stderr.read().decode().strip()
        if err:
            print(f"[-] PVE 設定回報警告: {err}")
        else:
            print(f"[+] LXC {lxc_id} 開機自啟動設定成功！")
            
        # 2. 在 LXC 容器內建立 systemd 服務檔
        print(f"[*] 正在 LXC {lxc_id} 內建置 minecraft.service 系統守護服務...")
        
        service_content = """[Unit]
Description=Minecraft Server
After=network.target

[Service]
Type=forking
WorkingDirectory=/root/minecraft
ExecStart=/usr/bin/screen -dmS mc bash run.sh
ExecStop=/usr/bin/screen -S mc -X eval 'stuff "stop\\n"'
TimeoutStopSec=30
Restart=always

[Install]
WantedBy=multi-user.target"""

        # 逸出單引號與寫入
        cmd_write_service = f"pct exec {lxc_id} -- bash -c \"cat << 'EOF' > /etc/systemd/system/minecraft.service\n{service_content}\nEOF\""
        stdin, stdout, stderr = client.exec_command(cmd_write_service)
        err = stderr.read().decode().strip()
        if err:
            print(f"[-] 寫入服務檔時發生錯誤: {err}")
            return
            
        # 3. 啟用並啟動服務
        print(f"[*] 正在啟用並重載 LXC {lxc_id} 的 systemd 服務...")
        cmd_enable = f"pct exec {lxc_id} -- bash -c 'systemctl daemon-reload && systemctl enable minecraft.service && systemctl restart minecraft.service'"
        stdin, stdout, stderr = client.exec_command(cmd_enable)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        
        print(f"    執行輸出: {out}")
        if err:
            print(f"    執行警告: {err}")
            
        # 4. 驗證服務狀態
        print(f"[*] 正在確認服務狀態...")
        stdin, stdout, stderr = client.exec_command(f"pct exec {lxc_id} -- systemctl status minecraft.service | head -n 5")
        status_out = stdout.read().decode().strip()
        print(f"    服務狀態:\n{status_out}")
        
        print("\n[+] 全鏈路自動啟動配置完成！")
        print("    1. 當 Proxmox 宿主機開機時，LXC 102 容器將自動啟動。")
        print("    2. 當 LXC 102 容器啟動時，Minecraft 伺服器將透過 systemd 自動於 screen 背景執行，並在崩潰時自動重啟。")
        print("    3. 當容器關機時，systemd 會自動對 screen 發送 'stop' 命令，安全存檔防世界毀損。")

    except Exception as e:
        print(f"[-] 發生錯誤: {e}")
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    configure_autostart()
