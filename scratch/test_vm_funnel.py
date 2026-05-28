import paramiko
import time

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("1. Checking QEMU Guest Agent on VM 100...")
stdin, stdout, stderr = pve_client.exec_command("qm guest exec 100 -- tailscale version")
print("TS Version in VM:", stdout.read().decode())
print("Error:", stderr.read().decode())

print("2. Starting tailscale serve/funnel in VM 100...")
pve_client.exec_command("qm guest exec 100 -- tailscale funnel reset")
time.sleep(1)

stdin, stdout, stderr = pve_client.exec_command("qm guest exec 100 -- tailscale funnel --bg 8000")
print("Funnel Start Output:", stdout.read().decode())
print("Funnel Start Error:", stderr.read().decode())

time.sleep(1)
stdin, stdout, stderr = pve_client.exec_command("qm guest exec 100 -- tailscale funnel status")
print("Funnel Status in VM:", stdout.read().decode())

pve_client.close()
