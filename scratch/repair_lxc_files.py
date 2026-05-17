import paramiko

def force_re_extract():
    px_ip = '192.168.0.138'
    px_user = 'root'
    px_pass = 'deven951130'
    lxc_ip = '192.168.0.108'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Connecting to Proxmox...")
        client.connect(px_ip, username=px_user, password=px_pass, timeout=10)
        
        # 使用 Proxmox 權限強制將 VM 100 內的檔案推送到 LXC 102 (如果沒推成功)
        # 或者從 Windows 重新上傳一次，因為剛剛發現 /root/minecraft 是空的
        print("Re-preparing LXC 102 directory...")
        client.exec_command('pct exec 102 -- mkdir -p /root/minecraft')
        
        print("Done preparing. Now need to re-upload from Windows.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    force_re_extract()
