import paramiko
import time

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Starting retry loop for Funnel...")
for i in range(30): # try for 30 * 10 = 300 seconds (5 minutes)
    stdin, stdout, stderr = pve_client.exec_command("tailscale funnel --bg 8000")
    out = stdout.read().decode()
    if "Funnel is not enabled" not in out:
        print("Success!")
        break
    time.sleep(10)

pve_client.close()
