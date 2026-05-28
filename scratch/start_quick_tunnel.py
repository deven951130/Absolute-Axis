import paramiko
import time
import re

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Downloading cloudflared to PVE...")
pve_client.exec_command("wget -qO /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64")
pve_client.exec_command("chmod +x /tmp/cloudflared")

print("Killing existing quick tunnels...")
pve_client.exec_command("pkill -f 'cloudflared tunnel --url'")

print("Starting Quick Tunnel to 192.168.0.159:8000...")
# run in background and capture log
pve_client.exec_command("nohup /tmp/cloudflared tunnel --url http://192.168.0.159:8000 > /tmp/cf_tunnel.log 2>&1 &")

time.sleep(5)
print("Reading tunnel URL from log...")
stdin, stdout, stderr = pve_client.exec_command("cat /tmp/cf_tunnel.log")
log_content = stdout.read().decode()

urls = re.findall(r'https://[-a-zA-Z0-9]+\.trycloudflare\.com', log_content)
if urls:
    print(f"SUCCESS: Quick Tunnel URL is {urls[-1]}")
else:
    print("FAILED to find URL. Log content:")
    print(log_content)

pve_client.close()
