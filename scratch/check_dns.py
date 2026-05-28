import socket
import paramiko
import requests

try:
    ip = socket.gethostbyname('absoluteaxis.dpdns.org')
    print(f"Windows Local DNS: absoluteaxis.dpdns.org resolves to {ip}")
except Exception as e:
    print(f"Windows Local DNS Error: {e}")

try:
    pve_client = paramiko.SSHClient()
    pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

    stdin, stdout, stderr = pve_client.exec_command("ping -c 1 absoluteaxis.dpdns.org")
    print("PVE DNS:\n", stdout.read().decode())
    
    stdin, stdout, stderr = pve_client.exec_command("curl -k -s https://absoluteaxis.dpdns.org")
    print("CURL response:\n", stdout.read().decode())
    
    pve_client.close()
except Exception as e:
    print("PVE Check Error:", e)
