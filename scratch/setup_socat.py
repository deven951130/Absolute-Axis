import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Killing existing socat processes on port 80 (if any)...")
pve_client.exec_command("fuser -k 80/tcp")
pve_client.exec_command("killall socat")

print("Starting socat to forward PVE:80 to VM:8000...")
# 使用 nohup 或背景執行
pve_client.exec_command("nohup socat TCP4-LISTEN:80,fork,reuseaddr TCP4:192.168.0.159:8000 > /dev/null 2>&1 &")

print("Checking if socat is running...")
stdin, stdout, stderr = pve_client.exec_command("ss -tapn | grep :80")
print(stdout.read().decode())

pve_client.close()
