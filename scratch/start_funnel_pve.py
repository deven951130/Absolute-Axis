import paramiko
import time

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("1. Cleaning old connections...")
pve_client.exec_command("killall socat")
pve_client.exec_command("tailscale funnel off")
pve_client.exec_command("tailscale serve reset")

time.sleep(1)

print("2. Starting internal port forwarding...")
# Forward PVE's local 8000 to VM's 8000
pve_client.exec_command("nohup socat TCP4-LISTEN:8000,fork,reuseaddr TCP4:192.168.0.159:8000 > /dev/null 2>&1 &")

time.sleep(1)

print("3. Starting Tailscale Funnel...")
# Tell Tailscale to serve HTTPS on 443 and proxy it to the internal 8000
stdin, stdout, stderr = pve_client.exec_command("tailscale serve https / http://127.0.0.1:8000")
print("Serve Config:", stdout.read().decode())

stdin, stdout, stderr = pve_client.exec_command("tailscale funnel 443 on")
print("Funnel Start:", stdout.read().decode())

print("4. Funnel Status:")
stdin, stdout, stderr = pve_client.exec_command("tailscale funnel status")
print(stdout.read().decode())

pve_client.close()
