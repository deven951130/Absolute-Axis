import paramiko
import time

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("1. Killing old socat and funnel processes...")
pve_client.exec_command("fuser -k 80/tcp")
pve_client.exec_command("killall socat")

print("2. Starting socat to forward PVE:80 to VM:8000...")
pve_client.exec_command("nohup socat TCP4-LISTEN:80,fork,reuseaddr TCP4:192.168.0.159:8000 > /dev/null 2>&1 &")

time.sleep(1)

print("3. Starting Tailscale Funnel...")
# 使用最新的 tailscale serve 語法
# 將 443 (https) 的流量轉到本機的 80
stdin, stdout, stderr = pve_client.exec_command("tailscale funnel 80")
print("Funnel Start Output:", stdout.read().decode())
print("Funnel Start Error:", stderr.read().decode())

print("4. Checking status...")
stdin, stdout, stderr = pve_client.exec_command("tailscale funnel status")
print(stdout.read().decode())

pve_client.close()
