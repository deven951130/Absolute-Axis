import paramiko
import time

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("1. Cleaning old connections...")
pve_client.exec_command("killall socat")
pve_client.exec_command("tailscale funnel reset")

time.sleep(1)

print("2. Starting internal port forwarding...")
pve_client.exec_command("nohup socat TCP4-LISTEN:8000,fork,reuseaddr TCP4:192.168.0.159:8000 > /dev/null 2>&1 &")

time.sleep(1)

print("3. Starting Tailscale Funnel...")
stdin, stdout, stderr = pve_client.exec_command("tailscale funnel --bg 8000")
print("Funnel Start:", stdout.read().decode())
print("Funnel Error:", stderr.read().decode())

time.sleep(1)

print("4. Funnel Status:")
stdin, stdout, stderr = pve_client.exec_command("tailscale funnel status")
print(stdout.read().decode())

pve_client.close()
