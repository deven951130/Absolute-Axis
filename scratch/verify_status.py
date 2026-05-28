import paramiko
import requests
import json

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("1. Checking VM 8000 port from PVE...")
stdin, stdout, stderr = pve_client.exec_command("curl -sI http://192.168.0.159:8000/")
print(stdout.read().decode())

print("2. Checking PVE socat processes...")
stdin, stdout, stderr = pve_client.exec_command("ss -tapn | grep '80\\|443'")
print(stdout.read().decode())

pve_client.close()

print("\n3. Checking DNS resolution from Windows host...")
try:
    import socket
    ip = socket.gethostbyname('absoluteaxis.dpdns.org')
    print(f"absoluteaxis.dpdns.org resolves to: {ip}")
except Exception as e:
    print(f"DNS Resolution error: {e}")
