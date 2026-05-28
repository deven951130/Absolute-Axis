import paramiko

def test_ssh(ip, username, password):
    print(f"Testing SSH to {ip} as {username}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, username=username, password=password, timeout=5)
        print(f"SUCCESS: Connected to {ip} as {username}")
        stdin, stdout, stderr = client.exec_command("whoami && pwd")
        print("Output:", stdout.read().decode().strip())
        client.close()
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

# 測試直接連接 VM 100 的 IP (192.168.0.159)
test_ssh('192.168.0.159', 'sparkle', 'deven951130')
test_ssh('192.168.0.159', 'root', 'deven951130')

# 也測試看看 PVE 100.124.203.61 是否可以 SSH 連到 192.168.0.159
print("Testing via PVE Host...")
pve = paramiko.SSHClient()
pve.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    pve.connect('100.124.203.61', username='root', password='deven951130', timeout=5)
    # 在 PVE 上嘗試 ssh 到 192.168.0.159
    # 我們可以用 sshpass 或是簡單的 ssh 測試 ping
    stdin, stdout, stderr = pve.exec_command("ping -c 1 192.168.0.159")
    print("Ping VM from PVE:", stdout.read().decode())
    
    # 嘗試在 PVE 上使用 ssh 登入 VM
    # 使用 sshpass 傳遞密碼
    cmd = "sshpass -p 'deven951130' ssh -o StrictHostKeyChecking=no sparkle@192.168.0.159 'whoami && pwd'"
    stdin, stdout, stderr = pve.exec_command(cmd)
    print("SSH via sshpass output:", stdout.read().decode())
    print("SSH via sshpass stderr:", stderr.read().decode())
    
    pve.close()
except Exception as e:
    print(f"PVE connection failed: {e}")
