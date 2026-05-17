import paramiko
import sys

def run_ssh_command(ip, username, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, username=username, password=password, timeout=5)
        stdin, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        return out, err
    except Exception as e:
        return None, str(e)
    finally:
        client.close()

def run_diagnostics():
    lxc_ip = '192.168.0.108'
    print(f"=== 診斷 LXC 容器 ({lxc_ip}) ===")
    
    # 1. 檢查埠監聽狀態
    print("[1] 檢查埠 25565 監聽狀態...")
    out, err = run_ssh_command(lxc_ip, 'root', '951130', 'ss -tulpn | grep 25565')
    if out:
        print(f"監聽狀態:\n{out}")
    else:
        print(f"未找到 25565 監聽，或錯誤: {err}")
        
    # 2. 檢查網路路由與閘道器
    print("\n[2] 檢查網路路由與閘道器...")
    out, err = run_ssh_command(lxc_ip, 'root', '951130', 'ip route')
    if out:
        print(f"路由表:\n{out}")
    else:
        print(f"無法讀取路由表: {err}")
        
    # 3. 檢查 UFW 防火牆狀態
    print("\n[3] 檢查 UFW 防火牆狀態...")
    out, err = run_ssh_command(lxc_ip, 'root', '951130', 'ufw status')
    if out:
        print(f"UFW 狀態: {out}")
    else:
        print(f"UFW 檢查錯誤: {err}")

    # 4. 檢查 iptables 規則
    print("\n[4] 檢查 iptables 規則...")
    out, err = run_ssh_command(lxc_ip, 'root', '951130', 'iptables -L -n -v | grep -E "25565|DROP|REJECT"')
    if out:
        print(f"iptables 相關規則:\n{out}")
    else:
        print(f"iptables 相關規則無輸出或錯誤: {err}")

    # 5. 讀取 server.properties 中的伺服器 IP 設定
    print("\n[5] 檢查 server.properties 配置...")
    out, err = run_ssh_command(lxc_ip, 'root', '951130', 'find / -name "server.properties" 2>/dev/null')
    if out:
        paths = out.split('\n')
        for path in paths:
            if not path.strip():
                continue
            print(f"找到設定檔: {path}")
            prop_out, prop_err = run_ssh_command(lxc_ip, 'root', '951130', f'grep -E "server-ip|server-port|query.port" {path}')
            print(f"配置內容:\n{prop_out}")
    else:
        print("找不到 server.properties 檔案。")

if __name__ == "__main__":
    run_diagnostics()
